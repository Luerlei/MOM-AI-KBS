<template>
  <div class="knowledge-detail" v-if="data">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <a-space>
        <a-button type="primary" @click="goEdit">
          <EditOutlined />编辑
        </a-button>
        <a-popconfirm title="确定删除此知识?" @confirm="handleDelete">
          <a-button danger>
            <DeleteOutlined />删除
          </a-button>
        </a-popconfirm>
        <a-button @click="$router.push('/knowledge')">
          <ArrowLeftOutlined />返回列表
        </a-button>
      </a-space>
    </div>
    <a-row :gutter="16">
      <!-- 主内容 -->
      <a-col :xs="24" :lg="17">
        <a-card>
          <!-- 标题 -->
          <div class="detail-header">
            <h1 class="detail-title">{{ data.title }}</h1>
            <div class="detail-meta">
              <span class="meta-label">分类：</span>
              <a-tag v-if="data.category_name" color="blue">
                {{ data.category_name }}
              </a-tag>
              <span v-else class="meta-empty">未分类</span>
              <a-divider type="vertical" />
              <span class="meta-label">标签：</span>
              <template v-if="data.tags && data.tags.length > 0">
                <a-tag
                  v-for="tag in data.tags"
                  :key="tag.id"
                  :color="tag.color || 'default'"
                >
                  {{ tag.name }}
                </a-tag>
              </template>
              <span v-else class="meta-empty">无标签</span>
              <a-divider type="vertical" />
              <span class="meta-text">
                类型：{{ contentTypeText(data.content_type) }}
                <a-tag
                  :color="statusColor(data.status)"
                  style="margin-left: 8px; font-size: 12px"
                >
                  {{ statusText(data.status) }}
                </a-tag>
                <a-tag v-if="data.vector_indexed === true" color="success" style="margin-left: 8px; font-size: 12px">
                  已索引
                </a-tag>
                <a-tag v-else-if="data.vector_indexed === false" color="warning" style="margin-left: 8px; font-size: 12px">
                  未索引
                </a-tag>
              </span>
              <a-divider type="vertical" />
              <span class="meta-text">创建于 {{ formatTime(data.created_at) }}</span>
              <span class="meta-text" v-if="data.updated_at !== data.created_at">
                · 更新于 {{ formatTime(data.updated_at) }}
              </span>
            </div>
          </div>
          <a-divider />
          <!-- 附件信息 -->
          <a-card v-if="data?.documents && data.documents.length > 0" title="原始附件" size="small" class="detail-card">
            <a-list :data-source="data.documents" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta :title="item.filename">
                    <template #description>
                      <span>{{ item.file_type?.toUpperCase() }} · {{ formatSize(item.file_size) }}</span>
                    </template>
                  </a-list-item-meta>
                  <template #actions>
                    <a-button type="link" size="small" @click="downloadDoc(item)">
                      <DownloadOutlined />下载
                    </a-button>
                  </template>
                </a-list-item>
              </template>
            </a-list>
          </a-card>
          <a-divider />
          <!-- 内容 / 分块 Tab -->
          <a-tabs v-model:activeKey="activeTab">
            <a-tab-pane key="content" tab="正文内容">
              <div class="detail-content">
                <MarkdownView v-if="data.content_type === 'markdown'" :content="data.content" />
                <div v-else-if="data.content_type === 'html'" v-html="sanitizedHtml"></div>
                <pre v-else class="plain-text">{{ data.content }}</pre>
              </div>
            </a-tab-pane>
            <a-tab-pane key="chunks" :tab="`向量分块 (${chunks.length})`">
              <a-spin :spinning="chunksLoading">
                <div class="chunks-toolbar" style="margin-bottom: 12px;">
                  <a-space wrap>
                    <a-button size="small" :loading="rebuildLoading" @click="handleRebuildIndex">
                      <ReloadOutlined />重建索引
                    </a-button>
                    <a-tooltip title="分块大小 500 字符，重叠 50 字符。重建索引会重新分块并生成 Embedding。">
                      <InfoCircleOutlined style="color: rgba(0,0,0,0.45)" />
                    </a-tooltip>
                    <a-divider type="vertical" />
                    <span v-if="chunksEmbeddingModel" class="chunk-meta-info">
                      <a-tag color="purple" size="small">{{ chunksEmbeddingModel }}</a-tag>
                      <span v-if="chunksEmbeddingDim" class="chunk-meta">维度 {{ chunksEmbeddingDim }}</span>
                    </span>
                    <span v-if="chunksIndexedAt" class="chunk-meta">索引于 {{ formatTime(chunksIndexedAt) }}</span>
                  </a-space>
                </div>
                <!-- chunk 检索测试面板 -->
                <div class="chunk-test-panel" style="margin-bottom: 12px;">
                  <a-input-group compact>
                    <a-input
                      v-model:value="testQuery"
                      placeholder="输入测试查询，查看命中的分块及得分..."
                      style="width: calc(100% - 80px)"
                      allow-clear
                      @press-enter="runTestRetrieval"
                    />
                    <a-button
                      type="primary"
                      size="small"
                      style="width: 80px"
                      :loading="testLoading"
                      :disabled="!testQuery.trim()"
                      @click="runTestRetrieval"
                    >
                      <SearchOutlined />测试
                    </a-button>
                  </a-input-group>
                  <div v-if="testHits.length > 0" class="test-hits-info" style="margin-top: 8px;">
                    <a-alert type="info" show-icon :message="`命中 ${testHits.length} 个分块（按得分排序）`" />
                  </div>
                </div>
                <a-empty v-if="!chunksLoading && chunks.length === 0" description="暂无向量分块（未索引或未配置 Embedding 模型）" />
                <div v-else class="chunk-list">
                  <a-card
                    v-for="chunk in chunks"
                    :key="chunk.id"
                    size="small"
                    class="chunk-card"
                    :class="{ 'chunk-hit': chunk._hit }"
                  >
                    <template #title>
                      <span class="chunk-title">
                        <a-tag color="blue">分块 #{{ chunk.chunk_index }}</a-tag>
                        <span class="chunk-meta">{{ chunk.char_count }} 字符</span>
                        <a-tag v-if="chunk._score != null" color="orange" size="small">
                          得分 {{ (chunk._score * 100).toFixed(1) }}%
                        </a-tag>
                      </span>
                    </template>
                    <div class="chunk-content">{{ chunk.document }}</div>
                  </a-card>
                </div>
              </a-spin>
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </a-col>

      <!-- 侧边栏：相关推荐 -->
      <a-col :xs="24" :lg="7">
        <a-card title="相关推荐" class="related-card">
          <a-spin :spinning="relatedLoading">
            <a-empty v-if="!relatedLoading && relatedList.length === 0" description="暂无相关内容" />
            <a-list :data-source="relatedList" item-layout="horizontal">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <a @click="goRelated(item.id)">{{ item.title }}</a>
                    </template>
                    <template #description>
                      <div class="related-meta">
                        <a-tag v-if="item.category_name" color="blue" size="small">
                          {{ item.category_name }}
                        </a-tag>
                        <span>{{ truncateText(stripMd(item.content), 60) }}</span>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-spin>
        </a-card>
      </a-col>
    </a-row>
  </div>
  <a-spin v-else-if="loading" tip="加载中..." class="loading-spin" />
</template>

<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EditOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
  DownloadOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import MarkdownView from '@/components/MarkdownView.vue'
import DOMPurify from 'dompurify'
import {
  getKnowledgeDetail,
  getRelatedKnowledge,
  getDownloadUrl,
  deleteKnowledge,
  getKnowledgeChunks,
  rebuildSingleIndex,
  testChunkRetrieval,
  type KnowledgeChunk
} from '@/api/knowledge'
import type { Knowledge } from '@/types'

const route = useRoute()
const router = useRouter()

// XSS 防护：对 HTML 类型内容进行 DOMPurify 过滤后再渲染
const sanitizedHtml = computed(() => {
  if (!data.value || data.value.content_type !== 'html') return ''
  return DOMPurify.sanitize(data.value.content, {
    ALLOWED_TAGS: ['p', 'br', 'b', 'i', 'u', 's', 'strong', 'em', 'a', 'ul', 'ol', 'li',
      'table', 'thead', 'tbody', 'tr', 'td', 'th', 'img', 'div', 'span', 'h1', 'h2',
      'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre', 'hr'],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'width', 'height', 'style', 'class'],
    ALLOW_DATA_ATTR: false,
  })
})

const loading = ref(false)
const relatedLoading = ref(false)
const chunksLoading = ref(false)
const rebuildLoading = ref(false)
const data = ref<Knowledge | null>(null)
const relatedList = ref<Knowledge[]>([])
const chunks = ref<KnowledgeChunk[]>([])
const activeTab = ref('content')

// chunk 检索测试
const testQuery = ref('')
const testLoading = ref(false)
const testHits = ref<Array<{ id: string; chunk_index: number; score: number; document: string }>>([])

async function runTestRetrieval(): Promise<void> {
  if (!data.value || !testQuery.value.trim()) return
  testLoading.value = true
  try {
    const res = await testChunkRetrieval(data.value.id, testQuery.value.trim(), 5)
    testHits.value = res.hits || []
    // 高亮命中的 chunk
    const hitIds = new Set(testHits.value.map((h) => h.id))
    const scoreMap = new Map(testHits.value.map((h) => [h.id, h.score]))
    chunks.value = chunks.value.map((c) => ({
      ...c,
      _hit: hitIds.has(c.id),
      _score: scoreMap.get(c.id),
    }))
    if (testHits.value.length === 0) {
      message.info('未命中任何分块')
    }
  } catch {
    testHits.value = []
    message.error('检索测试失败')
  } finally {
    testLoading.value = false
  }
}

// embedding 元信息（从第一个 chunk 的 metadata 提取）
const chunksEmbeddingModel = computed(() => {
  const first = chunks.value[0]
  return (first?.metadata as Record<string, unknown>)?.embedding_model as string || ''
})
const chunksEmbeddingDim = computed(() => {
  const first = chunks.value[0]
  return (first?.metadata as Record<string, unknown>)?.embedding_dim as number || 0
})
const chunksIndexedAt = computed(() => {
  const first = chunks.value[0]
  return (first?.metadata as Record<string, unknown>)?.indexed_at as string || ''
})

async function fetchDetail(id: number): Promise<void> {
  loading.value = true
  data.value = null
  try {
    data.value = await getKnowledgeDetail(id)
    fetchRelated(id)
    fetchChunks(id)
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchChunks(id: number): Promise<void> {
  chunksLoading.value = true
  try {
    const res = await getKnowledgeChunks(id)
    chunks.value = (res.chunks || []).map((c: KnowledgeChunk) => ({ ...c, _hit: false, _score: undefined as number | undefined }))
  } catch {
    chunks.value = []
  } finally {
    chunksLoading.value = false
  }
}

async function handleRebuildIndex(): Promise<void> {
  if (!data.value) return
  rebuildLoading.value = true
  try {
    const res = await rebuildSingleIndex(data.value.id)
    if (res.success) {
      message.success('索引重建成功')
      fetchChunks(data.value.id)
    } else {
      message.warning('索引重建失败（可能未配置 Embedding 或状态非已发布）')
    }
  } catch {
    // ignore
  } finally {
    rebuildLoading.value = false
  }
}

async function fetchRelated(id: number): Promise<void> {
  relatedLoading.value = true
  try {
    relatedList.value = await getRelatedKnowledge(id)
  } catch {
    relatedList.value = []
  } finally {
    relatedLoading.value = false
  }
}

function goEdit(): void {
  if (data.value) {
    router.push(`/knowledge/edit/${data.value.id}`)
  }
}

async function handleDelete(): Promise<void> {
  if (!data.value) return
  try {
    await deleteKnowledge(data.value.id)
    message.success('删除成功')
    router.push('/knowledge')
  } catch {
    // ignore
  }
}

async function downloadDoc(doc: { id: number; filename: string }): Promise<void> {
  const kid = Number(route.params.id)
  const url = getDownloadUrl(kid, doc.id)
  try {
    const res = await fetch(url)
    if (!res.ok) {
      throw new Error(`下载失败: ${res.status}`)
    }
    const blob = await res.blob()
    // 优先用 attachment 头里的 filename
    const disp = res.headers.get('content-disposition') || ''
    let fname = doc.filename || 'download'
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disp)
    if (m && m[1]) {
      try { fname = decodeURIComponent(m[1]) } catch { /* keep */ }
    }
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = fname
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(objUrl), 1000)
  } catch (e) {
    message.error(`下载失败: ${(e as Error).message}`)
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function goRelated(rid: number): void {
  router.push(`/knowledge/detail/${rid}`)
}

function truncateText(text: string, max: number): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function stripMd(text: string): string {
  if (!text) return ''
  return text.replace(/[#*`_\-\[\]()>~]/g, '').replace(/\n+/g, ' ').trim()
}

function contentTypeText(type: string): string {
  const map: Record<string, string> = {
    markdown: 'Markdown',
    text: '纯文本',
    html: 'HTML'
  }
  return map[type] || type
}

function statusText(status: string | undefined): string {
  const map: Record<string, string> = {
    published: '已发布',
    draft: '草稿',
    archived: '已归档'
  }
  return map[status || 'published'] || '已发布'
}

function statusColor(status: string | undefined): string {
  const map: Record<string, string> = {
    published: 'success',
    draft: 'default',
    archived: 'warning'
  }
  return map[status || 'published'] || 'success'
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

watch(
  () => route.params.id,
  (id) => {
    if (id) {
      fetchDetail(Number(id))
    }
  }
)

onMounted(() => {
  const id = route.params.id
  if (id) {
    fetchDetail(Number(id))
  }
})
</script>

<style scoped>
.knowledge-detail {
  max-width: 1400px;
  margin: 0 auto;
}

.page-toolbar {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.detail-header {
  margin-bottom: 8px;
}

.detail-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 12px;
  color: rgba(0, 0, 0, 0.88);
}

.detail-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.45);
}

.meta-label {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  font-weight: 500;
}

.meta-empty {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.35);
  font-style: italic;
}

.meta-text {
  font-size: 13px;
}

.detail-content {
  min-height: 200px;
  line-height: 1.8;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-card {
  background: #fafafa;
}

.chunk-hit {
  background: #fffbe6;
  border-color: #ffe58f;
}

.chunk-meta-info {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.chunk-test-panel {
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.chunk-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chunk-meta {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.chunk-content {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(0, 0, 0, 0.75);
  max-height: 300px;
  overflow-y: auto;
}

.plain-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  background: transparent;
  padding: 0;
  margin: 0;
}

.related-card {
  position: sticky;
  top: 80px;
}

.related-meta {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.loading-spin {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.detail-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
