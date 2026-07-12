<template>
  <div class="knowledge-list">
    <a-row :gutter="16">
      <!-- 左侧筛选 -->
      <a-col :xs="24" :md="6" :lg="5">
        <a-card title="筛选" size="small" class="filter-card">
          <!-- 分类 -->
          <div class="filter-section">
            <div class="section-title-row">
              <span class="section-title">分类</span>
            </div>
            <CategoryTree
              :categories="categories"
              :selected-id="query.category_id"
              :loading="categoryLoading"
              @select="onCategorySelect"
              @refresh="fetchCategories"
            />
          </div>
          <a-divider style="margin: 12px 0" />
          <!-- 标签 -->
          <div class="filter-section">
            <div class="section-title-row">
              <span class="section-title">标签</span>
            </div>
            <a-spin :spinning="tagLoading">
              <div class="tag-radio-group">
                <label
                  class="tag-radio-item"
                  :class="{ 'tag-radio-active': !query.tag_ids?.length }"
                  @click="clearTags"
                >
                  <span>全部</span>
                </label>
                <label
                  v-for="tag in tags"
                  :key="tag.id"
                  class="tag-radio-item"
                  :class="{ 'tag-radio-active': query.tag_ids?.includes(tag.id) }"
                  @click="onTagToggle(tag.id)"
                >
                  <span>{{ tag.name }}</span>
                </label>
              </div>
              <a-empty v-if="!tagLoading && tags.length === 0" :image="simpleImage" />
            </a-spin>
          </div>
          <a-divider style="margin: 12px 0" />
          <a-button block @click="resetFilters">重置筛选</a-button>
        </a-card>
      </a-col>

      <!-- 右侧列表 -->
      <a-col :xs="24" :md="18" :lg="19">
        <a-card :body-style="{ padding: '0' }">
          <!-- 顶部操作栏 -->
          <div class="toolbar">
            <a-input-search
              v-model:value="query.keyword"
              placeholder="搜索标题或内容"
              style="width: 320px"
              allow-clear
              @search="fetchData"
            />
            <div class="toolbar-right">
              <a-space>
                <a-button type="primary" @click="$router.push('/knowledge/edit')">
                  <PlusOutlined />新建
                </a-button>
                <a-button @click="$router.push('/knowledge/upload')">
                  <CloudUploadOutlined />批量上传
                </a-button>
                <template v-if="selectedRowKeys.length > 0">
                  <a-divider type="vertical" />
                  <span class="selected-count">
                    已选 {{ selectedRowKeys.length }} 项
                  </span>
                  <a-button size="small" @click="openBatchTagModal">批量打标签</a-button>
                  <a-button size="small" @click="openBatchCategoryModal">移动分类</a-button>
                  <a-button size="small" danger @click="batchDelete">批量删除</a-button>
                </template>
              </a-space>
            </div>
          </div>

          <!-- 表格 -->
          <a-table
            :columns="columns"
            :data-source="tableData"
            :loading="loading"
            :pagination="pagination"
            :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
            :scroll="{ x: 1100 }"
            row-key="id"
            size="middle"
            @change="onTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a @click="goDetail(record.id)">{{ record.title }}</a>
              </template>
              <template v-else-if="column.key === 'content_type'">
                <a-tag :color="contentTypeColor(record.content_type)">
                  {{ contentTypeText(record.content_type) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'category_name'">
                <span v-if="record.category_name">{{ record.category_name }}</span>
                <span v-else class="text-muted">未分类</span>
              </template>
              <template v-else-if="column.key === 'tags'">
                <a-tag v-for="tag in record.tags" :key="tag.id" :color="tag.color || 'default'">
                  {{ tag.name }}
                </a-tag>
                <span v-if="!record.tags || record.tags.length === 0" class="text-muted">无</span>
              </template>
              <template v-else-if="column.key === 'created_at'">
                {{ formatTime(record.created_at) }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="goEdit(record.id)">编辑</a-button>
                  <a-popconfirm title="确定删除该知识条目?" @confirm="handleDelete(record.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <!-- 批量打标签弹窗 -->
    <a-modal
      v-model:open="batchTagVisible"
      title="批量打标签"
      @ok="confirmBatchTag"
      :confirm-loading="batchLoading"
    >
      <a-form layout="vertical">
        <a-form-item label="选择标签">
          <TagSelect
            v-model="batchTagIds"
            :tags="tags"
            placeholder="选择要添加的标签"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 批量移动分类弹窗 -->
    <a-modal
      v-model:open="batchCategoryVisible"
      title="批量移动分类"
      @ok="confirmBatchCategory"
      :confirm-loading="batchLoading"
    >
      <a-form layout="vertical">
        <a-form-item label="选择分类">
          <a-tree-select
            v-model:value="batchCategoryId"
            :tree-data="categoryTreeData"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择目标分类"
            allow-clear
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PlusOutlined, CloudUploadOutlined } from '@ant-design/icons-vue'
import { Empty, message, Modal } from 'ant-design-vue'
import dayjs from 'dayjs'
import CategoryTree from '@/components/CategoryTree.vue'
import TagSelect from '@/components/TagSelect.vue'
import {
  getKnowledgeList,
  deleteKnowledge,
  batchOperateKnowledge
} from '@/api/knowledge'
import { getCategoryTree, getTagList } from '@/api/category'
import type { Knowledge, KnowledgeQuery, Category, Tag, PaginatedData } from '@/types'

const router = useRouter()
const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE

const loading = ref(false)
const categoryLoading = ref(false)
const tagLoading = ref(false)
const batchLoading = ref(false)

const tableData = ref<Knowledge[]>([])
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const selectedRowKeys = ref<number[]>([])

const query = ref<KnowledgeQuery>({
  page: 1,
  page_size: 10,
  category_id: undefined,
  tag_ids: [],
  keyword: ''
})

const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
})

const columns = [
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true, width: 200 },
  { title: '类型', key: 'content_type', dataIndex: 'content_type', width: 100 },
  { title: '分类', key: 'category_name', dataIndex: 'category_name', width: 120 },
  { title: '标签', key: 'tags', dataIndex: 'tags', width: 180 },
  { title: '创建时间', key: 'created_at', dataIndex: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const }
]

// 扁平化分类树用于 tree-select
const categoryTreeData = computed<Category[]>(() => categories.value)

const batchTagVisible = ref(false)
const batchCategoryVisible = ref(false)
const batchTagIds = ref<number[]>([])
const batchCategoryId = ref<number | null>(null)

function onCategorySelect(categoryId: number | null): void {
  query.value.category_id = categoryId || undefined
  query.value.page = 1
  fetchData()
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
  fetchData()
}

function clearTags(): void {
  query.value.tag_ids = []
  query.value.page = 1
  fetchData()
}

function resetFilters(): void {
  query.value.category_id = undefined
  query.value.tag_ids = []
  query.value.keyword = ''
  query.value.page = 1
  fetchData()
}

function onSelectChange(keys: number[]): void {
  selectedRowKeys.value = keys
}

function onTableChange(pag: { current?: number; pageSize?: number }): void {
  query.value.page = pag.current
  query.value.page_size = pag.pageSize
  pagination.value.current = pag.current || 1
  pagination.value.pageSize = pag.pageSize || 10
  fetchData()
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res: PaginatedData<Knowledge> = await getKnowledgeList({
      page: query.value.page,
      page_size: query.value.page_size,
      category_id: query.value.category_id,
      tag_ids: query.value.tag_ids?.length ? query.value.tag_ids : undefined,
      keyword: query.value.keyword || undefined
    })
    tableData.value = res.items || []
    pagination.value.total = res.total || 0
    pagination.value.current = res.page || 1
  } catch {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

async function fetchCategories(): Promise<void> {
  categoryLoading.value = true
  try {
    categories.value = await getCategoryTree()
  } catch {
    // ignore
  } finally {
    categoryLoading.value = false
  }
}

async function fetchTags(): Promise<void> {
  tagLoading.value = true
  try {
    tags.value = await getTagList()
  } catch {
    // ignore
  } finally {
    tagLoading.value = false
  }
}

function goDetail(id: number): void {
  router.push(`/knowledge/detail/${id}`)
}

function goEdit(id: number): void {
  router.push(`/knowledge/edit/${id}`)
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteKnowledge(id)
    message.success('删除成功')
    fetchData()
  } catch {
    // ignore
  }
}

function openBatchTagModal(): void {
  batchTagIds.value = []
  batchTagVisible.value = true
}

function openBatchCategoryModal(): void {
  batchCategoryId.value = null
  batchCategoryVisible.value = true
}

async function confirmBatchTag(): Promise<void> {
  if (batchTagIds.value.length === 0) {
    message.warning('请选择至少一个标签')
    return
  }
  batchLoading.value = true
  try {
    await batchOperateKnowledge({
      ids: selectedRowKeys.value,
      action: 'add_tags',
      tag_ids: batchTagIds.value
    })
    message.success('批量打标签成功')
    batchTagVisible.value = false
    selectedRowKeys.value = []
    fetchData()
  } catch {
    // ignore
  } finally {
    batchLoading.value = false
  }
}

async function confirmBatchCategory(): Promise<void> {
  if (batchCategoryId.value === null) {
    message.warning('请选择分类')
    return
  }
  batchLoading.value = true
  try {
    await batchOperateKnowledge({
      ids: selectedRowKeys.value,
      action: 'set_category',
      category_id: batchCategoryId.value
    })
    message.success('批量移动分类成功')
    batchCategoryVisible.value = false
    selectedRowKeys.value = []
    fetchData()
  } catch {
    // ignore
  } finally {
    batchLoading.value = false
  }
}

function batchDelete(): void {
  Modal.confirm({
    title: '批量删除',
    content: `确定删除选中的 ${selectedRowKeys.value.length} 条知识吗？此操作不可恢复。`,
    okType: 'danger',
    onOk: async () => {
      try {
        await batchOperateKnowledge({
          ids: selectedRowKeys.value,
          action: 'delete'
        })
        message.success('批量删除成功')
        selectedRowKeys.value = []
        fetchData()
      } catch {
        // ignore
      }
    }
  })
}

function contentTypeText(type: string): string {
  const map: Record<string, string> = {
    markdown: 'Markdown',
    text: '文本',
    html: 'HTML'
  }
  return map[type] || type
}

function contentTypeColor(type: string): string {
  const map: Record<string, string> = {
    markdown: 'blue',
    text: 'default',
    html: 'orange'
  }
  return map[type] || 'default'
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchCategories()
  fetchTags()
  fetchData()
})
</script>

<style scoped>
.knowledge-list {
  min-height: 400px;
}

.filter-card {
  margin-bottom: 16px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section-title {
  font-weight: 600;
}

.tag-radio-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tag-radio-item {
  display: block;
  width: 100%;
  padding: 0 15px;
  height: 32px;
  line-height: 30px;
  font-size: 14px;
  text-align: left;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}

.tag-radio-item:hover {
  color: #1677ff;
  border-color: #1677ff;
}

.tag-radio-active {
  color: #fff;
  background: #1677ff;
  border-color: #1677ff;
}

.tag-radio-active:hover {
  color: #fff;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-count {
  color: #1677ff;
  font-weight: 500;
  margin-right: 4px;
}

.text-muted {
  color: rgba(0, 0, 0, 0.45);
}

@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
