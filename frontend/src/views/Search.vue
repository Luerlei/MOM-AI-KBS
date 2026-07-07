<template>
  <div class="search-page">
    <a-row :gutter="16">
      <!-- 左侧筛选 -->
      <a-col :xs="24" :md="6" :lg="5">
        <a-card title="二次筛选" size="small">
          <!-- 分类 -->
          <div class="filter-section">
            <div class="section-title">分类</div>
            <CategoryTree
              :categories="categories"
              :selected-id="query.category_id"
              @select="onCategorySelect"
            />
          </div>
          <a-divider style="margin: 12px 0" />
          <!-- 标签 -->
          <div class="filter-section">
            <div class="section-title">标签</div>
            <div class="tag-list">
              <a-checkable-tag
                v-for="tag in tags"
                :key="tag.id"
                :checked="query.tag_ids?.includes(tag.id)"
                @change="onTagToggle(tag.id)"
              >
                {{ tag.name }}
              </a-checkable-tag>
            </div>
          </div>
          <a-divider style="margin: 12px 0" />
          <!-- 时间范围 -->
          <div class="filter-section">
            <div class="section-title">时间范围</div>
            <a-range-picker
              v-model:value="dateRange"
              style="width: 100%; margin-bottom: 8px"
              :placeholder="['开始日期', '结束日期']"
              @change="onDateRangeChange"
            />
          </div>
          <a-divider style="margin: 12px 0" />
          <a-button block @click="resetFilters">重置</a-button>
        </a-card>

        <!-- 搜索历史 -->
        <a-card title="搜索历史" size="small" style="margin-top: 16px">
          <a-empty v-if="history.length === 0" :image="simpleImage" />
          <div v-else class="history-list">
            <div
              v-for="item in history"
              :key="item.id"
              class="history-item"
              @click="onHistoryClick(item.query)"
            >
              <a-tooltip :title="item.query">
                <span class="history-query">{{ item.query }}</span>
              </a-tooltip>
              <span class="history-meta">{{ formatTime(item.created_at) }}</span>
            </div>
          </div>
        </a-card>
      </a-col>

      <!-- 右侧搜索结果 -->
      <a-col :xs="24" :md="18" :lg="19">
        <a-card>
          <!-- 搜索框 -->
          <div class="search-box">
            <a-input-group compact>
              <a-select v-model:value="searchType" style="width: 100px">
                <a-select-option value="semantic">语义搜索</a-select-option>
                <a-select-option value="keyword">关键词</a-select-option>
              </a-select>
              <a-input-search
                v-model:value="query.query"
                placeholder="输入要搜索的内容..."
                style="width: calc(100% - 100px)"
                enter-button="搜索"
                @search="handleSearch"
                allow-clear
              />
            </a-input-group>
          </div>

          <!-- 搜索结果 -->
          <div class="results">
            <a-spin :spinning="loading">
              <a-empty
                v-if="!loading && results.length === 0"
                description="暂无搜索结果，请输入关键词搜索"
              />
              <div v-else>
                <div class="result-info">
                  共找到 <span class="highlight-num">{{ total }}</span> 条结果
                </div>
                <a-list :data-source="results" item-layout="vertical">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <a-list-item-meta>
                        <template #title>
                          <a @click="goDetail(item.id)" v-html="highlightTitle(item)"></a>
                        </template>
                        <template #description>
                          <div
                            class="result-snippet"
                            v-html="highlightSnippet(item)"
                          ></div>
                        </template>
                      </a-list-item-meta>
                      <template #actions>
                        <span v-if="item.category_name">
                          <a-tag color="blue">{{ item.category_name }}</a-tag>
                        </span>
                        <a-tag
                          v-for="tag in item.tags"
                          :key="tag.id"
                          :color="tag.color || 'default'"
                        >
                          {{ tag.name }}
                        </a-tag>
                        <span v-if="item.score" class="result-score">
                          相关度: {{ (item.score * 100).toFixed(1) }}%
                        </span>
                      </template>
                    </a-list-item>
                  </template>
                </a-list>

                <!-- 分页 -->
                <div class="pagination-wrap">
                  <a-pagination
                    v-model:current="query.page"
                    v-model:page-size="query.page_size"
                    :total="total"
                    :page-size-options="['10', '20', '50']"
                    show-size-changer
                    show-quick-jumper
                    @change="onPageChange"
                  />
                </div>
              </div>
            </a-spin>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import dayjs from 'dayjs'
import CategoryTree from '@/components/CategoryTree.vue'
import { semanticSearch, keywordSearch, getSearchHistory } from '@/api/search'
import { getCategoryTree, getTagList } from '@/api/category'
import type { SearchResult, SearchQuery, Category, Tag, SearchHistory } from '@/types'

const route = useRoute()
const router = useRouter()
const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE

const loading = ref(false)
const searchType = ref<'semantic' | 'keyword'>('semantic')
const results = ref<SearchResult[]>([])
const total = ref(0)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const history = ref<SearchHistory[]>([])

const query = ref<SearchQuery>({
  query: '',
  category_id: undefined,
  tag_ids: [],
  date_from: undefined,
  date_to: undefined,
  page: 1,
  page_size: 10
})
const dateRange = ref<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

function escapeHtml(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function highlightText(text: string): string {
  if (!text || !query.value.query) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const keywords = query.value.query
    .split(/\s+/)
    .filter((k) => k.length > 0)
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (keywords.length === 0) return escaped
  const pattern = new RegExp(`(${keywords.join('|')})`, 'gi')
  return escaped.replace(pattern, '<span class="highlight">$1</span>')
}

function highlightTitle(item: SearchResult): string {
  return highlightText(item.title)
}

function highlightSnippet(item: SearchResult): string {
  const text = item.snippet || item.highlight || item.content || ''
  const truncated = text.length > 300 ? text.slice(0, 300) + '...' : text
  return highlightText(truncated)
}

async function handleSearch(): Promise<void> {
  if (!query.value.query.trim()) {
    message.warning('请输入搜索内容')
    return
  }
  loading.value = true
  query.value.page = 1
  const params: SearchQuery = {
    query: query.value.query,
    category_id: query.value.category_id,
    tag_ids: query.value.tag_ids?.length ? query.value.tag_ids : undefined,
    date_from: query.value.date_from,
    date_to: query.value.date_to,
    page: 1,
    page_size: query.value.page_size
  }
  try {
    const res =
      searchType.value === 'semantic'
        ? await semanticSearch(params)
        : await keywordSearch(params)
    results.value = res.items || []
    total.value = res.total || 0
    fetchHistory()
  } catch (err: any) {
    results.value = []
    total.value = 0
    const msg = err?.response?.data?.message || err?.message || ''
    if (msg.includes('Embedding') || msg.includes('embedding')) {
      message.warning('未配置 Embedding 模型，已自动切换为关键词搜索')
      searchType.value = 'keyword'
      const fallback = await keywordSearch(params)
      results.value = fallback.items || []
      total.value = fallback.total || 0
    } else {
      message.error(msg || '搜索失败，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}

function onPageChange(page: number, pageSize: number): void {
  query.value.page = page
  query.value.page_size = pageSize
  doSearch()
}

async function doSearch(): Promise<void> {
  if (!query.value.query.trim()) return
  loading.value = true
  const params: SearchQuery = {
    query: query.value.query,
    category_id: query.value.category_id,
    tag_ids: query.value.tag_ids?.length ? query.value.tag_ids : undefined,
    date_from: query.value.date_from,
    date_to: query.value.date_to,
    page: query.value.page,
    page_size: query.value.page_size
  }
  try {
    const res =
      searchType.value === 'semantic'
        ? await semanticSearch(params)
        : await keywordSearch(params)
    results.value = res.items || []
    total.value = res.total || 0
  } catch (err: any) {
    results.value = []
    total.value = 0
    const msg = err?.response?.data?.message || err?.message || ''
    if (msg.includes('Embedding') || msg.includes('embedding')) {
      message.warning('未配置 Embedding 模型，已自动切换为关键词搜索')
      searchType.value = 'keyword'
      const fallback = await keywordSearch(params)
      results.value = fallback.items || []
      total.value = fallback.total || 0
    } else {
      message.error(msg || '搜索失败，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}

function onCategorySelect(categoryId: number | null): void {
  query.value.category_id = categoryId || undefined
  query.value.page = 1
  if (query.value.query) doSearch()
}

function onTagToggle(tagId: number): void {
  if (!query.value.tag_ids) query.value.tag_ids = []
  const idx = query.value.tag_ids.indexOf(tagId)
  if (idx >= 0) {
    query.value.tag_ids.splice(idx, 1)
  } else {
    query.value.tag_ids.push(tagId)
  }
  query.value.page = 1
  if (query.value.query) doSearch()
}

function resetFilters(): void {
  query.value.category_id = undefined
  query.value.tag_ids = []
  query.value.date_from = undefined
  query.value.date_to = undefined
  dateRange.value = null
  query.value.page = 1
  if (query.value.query) doSearch()
}

function onDateRangeChange(dates: [dayjs.Dayjs, dayjs.Dayjs] | null): void {
  if (dates && dates.length === 2) {
    query.value.date_from = dates[0].format('YYYY-MM-DD')
    query.value.date_to = dates[1].format('YYYY-MM-DD')
  } else {
    query.value.date_from = undefined
    query.value.date_to = undefined
  }
  query.value.page = 1
  if (query.value.query) doSearch()
}

function onHistoryClick(q: string): void {
  query.value.query = q
  query.value.page = 1
  handleSearch()
}

function goDetail(id: number): void {
  router.push(`/knowledge/detail/${id}`)
}

async function fetchCategories(): Promise<void> {
  try {
    categories.value = await getCategoryTree()
  } catch {
    // ignore
  }
}

async function fetchTags(): Promise<void> {
  try {
    tags.value = await getTagList()
  } catch {
    // ignore
  }
}

async function fetchHistory(): Promise<void> {
  try {
    history.value = await getSearchHistory()
  } catch {
    history.value = []
  }
}

function formatTime(time: string): string {
  return dayjs(time).format('MM-DD HH:mm')
}

watch(
  () => route.query.q,
  (q) => {
    if (q && typeof q === 'string') {
      query.value.query = q
      handleSearch()
    }
  },
  { immediate: true }
)

onMounted(() => {
  fetchCategories()
  fetchTags()
  fetchHistory()
  if (route.query.q) {
    query.value.query = route.query.q as string
    handleSearch()
  }
})
</script>

<style scoped>
.search-page {
  min-height: 400px;
}

.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.history-list {
  max-height: 240px;
  overflow-y: auto;
}

.history-item {
  padding: 6px 0;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item:hover {
  background: #fafafa;
}

.history-query {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.45);
}

.search-box {
  margin-bottom: 16px;
}

.result-info {
  margin-bottom: 12px;
  color: rgba(0, 0, 0, 0.65);
}

.highlight-num {
  color: #1677ff;
  font-weight: 600;
}

.result-snippet {
  color: rgba(0, 0, 0, 0.65);
  font-size: 13px;
  line-height: 1.6;
  margin: 4px 0;
}

.result-score {
  color: #faad14;
  font-size: 12px;
}

.pagination-wrap {
  margin-top: 16px;
  text-align: right;
}
</style>
