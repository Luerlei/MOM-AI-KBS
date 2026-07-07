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
              <span class="meta-text">类型：{{ contentTypeText(data.content_type) }}</span>
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
          <!-- 内容 -->
          <div class="detail-content">
            <MarkdownView v-if="data.content_type === 'markdown'" :content="data.content" />
            <div v-else-if="data.content_type === 'html'" v-html="data.content"></div>
            <pre v-else class="plain-text">{{ data.content }}</pre>
          </div>
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
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EditOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
  DownloadOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import MarkdownView from '@/components/MarkdownView.vue'
import { getKnowledgeDetail, getRelatedKnowledge, getDownloadUrl, deleteKnowledge } from '@/api/knowledge'
import type { Knowledge } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const relatedLoading = ref(false)
const data = ref<Knowledge | null>(null)
const relatedList = ref<Knowledge[]>([])

async function fetchDetail(id: number): Promise<void> {
  loading.value = true
  data.value = null
  try {
    data.value = await getKnowledgeDetail(id)
    fetchRelated(id)
  } catch {
    // ignore
  } finally {
    loading.value = false
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
