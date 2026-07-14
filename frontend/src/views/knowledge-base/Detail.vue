<template>
  <div class="kb-detail">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <a-button @click="$router.push('/knowledge-base')">
        <ArrowLeftOutlined />返回列表
      </a-button>
    </div>

    <a-spin :spinning="kbLoading" tip="加载中...">
      <template v-if="kb">
        <!-- 知识库信息 -->
        <a-card class="info-card">
          <div class="info-header">
            <h1 class="kb-title">{{ kb.name }}</h1>
            <a-tag v-if="kb.parse_on_upload" color="processing">上传自动解析</a-tag>
            <a-tag v-else>上传不解析</a-tag>
          </div>
          <div class="kb-desc">{{ kb.description || '暂无描述' }}</div>
          <div class="kb-meta">
            <span class="meta-item">
              <FileTextOutlined />
              <span>{{ kb.document_count || 0 }} 份资料</span>
            </span>
            <a-divider type="vertical" />
            <span class="meta-item">创建于 {{ formatTime(kb.created_at) }}</span>
          </div>
          <!-- 模型配置 -->
          <div class="kb-models">
            <a-tag color="blue">LLM: {{ kb.llm_model_name || '继承全局' }}</a-tag>
            <a-tag color="purple">Embedding: {{ kb.embedding_model_name || '继承全局' }}</a-tag>
            <a-tag color="cyan">Rerank: {{ kb.rerank_model_name || '继承全局' }}</a-tag>
            <a-tag color="orange">OCR: {{ kb.ocr_model_name || '继承全局' }}</a-tag>
            <a-tag color="magenta">VLM: {{ kb.vlm_model_name || '继承全局' }}</a-tag>
          </div>
        </a-card>

        <!-- 资料列表 -->
        <a-card class="docs-card">
          <template #title>
            资料列表
          </template>
          <template #extra>
            <a-button type="primary" @click="showUploadModal = true">
              <CloudUploadOutlined />上传资料
            </a-button>
          </template>
          <!-- 工具栏 -->
          <div class="docs-toolbar">
            <a-input-search
              v-model:value="docQuery.keyword"
              placeholder="搜索资料标题"
              style="width: 260px"
              allow-clear
              @search="onDocSearch"
            />
            <a-select
              v-model:value="docQuery.parse_status"
              placeholder="全部状态"
              allow-clear
              style="width: 140px"
              @change="onDocSearch"
            >
              <a-select-option value="pending">待解析</a-select-option>
              <a-select-option value="parsing">解析中</a-select-option>
              <a-select-option value="parsed">已解析</a-select-option>
              <a-select-option value="failed">解析失败</a-select-option>
            </a-select>
            <a-button
              v-if="selectedRowKeys.length > 0"
              type="primary"
              :loading="parseSelectedLoading"
              @click="handleParseSelected"
            >
              <ThunderboltOutlined />解析选中 ({{ selectedRowKeys.length }})
            </a-button>
            <a-button
              type="primary"
              ghost
              :loading="parseAllLoading"
              @click="handleParseAll"
            >
              <ThunderboltOutlined />批量解析全部
            </a-button>
          </div>

          <a-table
            :columns="docColumns"
            :data-source="documents"
            :loading="docLoading"
            :pagination="docPagination"
            :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
            row-key="id"
            size="middle"
            :scroll="{ x: 1100 }"
            @change="onDocTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a @click="viewDocument(record.id)">{{ record.title }}</a>
              </template>
              <template v-else-if="column.key === 'source_file'">
                <span v-if="record.source_file">{{ record.source_file }}</span>
                <span v-else class="text-muted">-</span>
              </template>
              <template v-else-if="column.key === 'parse_status'">
                <a-tag :color="parseStatusColor(record.parse_status)">
                  {{ parseStatusText(record.parse_status) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'created_at'">
                {{ formatTime(record.created_at) }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button
                    v-if="canParse(record.parse_status)"
                    type="link"
                    size="small"
                    :loading="parsingIds.includes(record.id)"
                    @click="handleParseDoc(record.id)"
                  >
                    解析
                  </a-button>
                  <a-button type="link" size="small" @click="viewDocument(record.id)">
                    查看
                  </a-button>
                  <a-popconfirm title="确定删除此资料？" @confirm="handleDeleteDoc(record.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </template>

      <a-result
        v-else-if="!kbLoading && loadError"
        status="error"
        title="加载失败"
        :sub-title="loadError"
      >
        <template #extra>
          <a-button type="primary" @click="$router.push('/knowledge-base')">返回列表</a-button>
        </template>
      </a-result>
    </a-spin>

    <!-- 上传资料弹窗 -->
    <a-modal
      v-model:open="showUploadModal"
      title="上传资料"
      width="720px"
      :footer="null"
      :mask-closable="false"
      @cancel="showUploadModal = false"
    >
      <a-upload-dragger
        :multiple="true"
        :before-upload="handleBeforeUpload"
        :show-upload-list="false"
        :accept="acceptTypes"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此处上传</p>
        <p class="ant-upload-hint">
          支持 .md / .txt / .pdf / .doc / .docx / .html / .xlsx / .csv 等格式
        </p>
      </a-upload-dragger>

      <div class="upload-actions">
        <a-button @click="triggerFolderSelect">
          <FolderOpenOutlined />上传文件夹
        </a-button>
        <input
          ref="folderInputRef"
          type="file"
          multiple
          style="display: none"
          @change="onFolderChange"
        />
      </div>

      <!-- 上传选项 -->
      <div class="upload-options">
        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-form-item label="解析方式">
              <a-switch
                v-model:checked="uploadOptions.parse_immediately"
                checked-children="立即解析"
                un-checked-children="仅上传"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="自动打标签">
              <a-switch v-model:checked="uploadOptions.auto_tag" />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="分类">
              <a-tree-select
                v-model:value="uploadOptions.category_id"
                :tree-data="categoryTreeData"
                :field-names="{ label: 'name', value: 'id', children: 'children' }"
                placeholder="选择分类（可选）"
                allow-clear
                tree-default-expand-all
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="标签">
              <TagSelect
                v-model="uploadOptions.tag_ids"
                :tags="tags"
                placeholder="选择标签（可选）"
                @create="onCreateTag"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </div>

      <!-- 待上传文件列表 -->
      <div v-if="pendingFiles.length > 0" class="pending-files">
        <div class="list-header">
          <span>待上传文件 ({{ pendingFiles.length }})</span>
          <a-button type="link" size="small" @click="clearPendingFiles">清空</a-button>
        </div>
        <a-table
          :columns="fileColumns"
          :data-source="pendingFileList"
          :pagination="false"
          size="small"
          row-key="uid"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <span class="file-name">
                <FileTextOutlined />
                <span>{{ record.name }}</span>
              </span>
            </template>
            <template v-else-if="column.key === 'size'">
              {{ formatSize(record.size) }}
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" size="small" danger @click="removePendingFile(record.uid)">
                移除
              </a-button>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 上传按钮 + 进度 -->
      <div class="upload-btn-area">
        <a-space>
          <a-button
            type="primary"
            :loading="uploading"
            :disabled="pendingFiles.length === 0"
            @click="handleUpload"
          >
            <CloudUploadOutlined />开始上传 ({{ pendingFiles.length }} 个文件)
          </a-button>
        </a-space>
        <div v-if="uploading" class="upload-progress">
          <a-spin tip="正在上传..." />
          <span class="progress-text">正在上传 {{ pendingFiles.length }} 个文件...</span>
        </div>
      </div>

      <!-- 上传结果 -->
      <div v-if="uploadResult" class="upload-result">
        <a-alert
          :message="`上传完成：成功 ${uploadResult.created} 个`"
          :description="uploadResultDesc"
          :type="uploadResult.failed.length > 0 ? 'warning' : 'success'"
          show-icon
          closable
          @close="uploadResult = null"
        />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftOutlined,
  InboxOutlined,
  FolderOpenOutlined,
  CloudUploadOutlined,
  FileTextOutlined,
  ThunderboltOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import TagSelect from '@/components/TagSelect.vue'
import {
  getKnowledgeBaseDetail,
  getKnowledgeBaseDocuments,
  uploadToKnowledgeBase,
  parseDocument,
  parseAllDocuments
} from '@/api/knowledgeBase'
import { deleteKnowledge } from '@/api/knowledge'
import { getCategoryTree, getTagList, createTag } from '@/api/category'
import type {
  Knowledge,
  KnowledgeBase,
  PaginatedData,
  ParseStatus,
  Category,
  Tag
} from '@/types'

const route = useRoute()
const router = useRouter()

type KbDocument = Knowledge & { parse_status?: ParseStatus }

const kbId = computed(() => Number(route.params.id))

const kbLoading = ref(false)
const kb = ref<KnowledgeBase | null>(null)
const loadError = ref('')

// 上传弹窗
const showUploadModal = ref(false)

// 文档列表
const docLoading = ref(false)
const documents = ref<KbDocument[]>([])
const docQuery = ref({
  keyword: '',
  parse_status: undefined as string | undefined,
  page: 1,
  page_size: 10
})
const docPagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
})
const parsingIds = ref<number[]>([])
const parseAllLoading = ref(false)
const selectedRowKeys = ref<number[]>([])
const parseSelectedLoading = ref(false)

// 上传
const folderInputRef = ref<HTMLInputElement | null>(null)
const pendingFiles = ref<File[]>([])
const uploading = ref(false)
const uploadResult = ref<{
  created: number
  skipped_duplicate: string[]
  failed: { filename: string; reason: string }[]
} | null>(null)

const acceptTypes = '.md,.txt,.pdf,.doc,.docx,.html,.xlsx,.xls,.csv,.ppt,.pptx,.png,.jpg,.jpeg'

const uploadOptions = ref({
  parse_immediately: true,
  auto_tag: false,
  category_id: null as number | null,
  tag_ids: [] as number[]
})

const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

const categoryTreeData = computed<Category[]>(() => categories.value)

// 待上传文件列表（用于 a-table 展示）
interface PendingFileItem {
  uid: string
  name: string
  size: number
  file: File
}

const pendingFileList = computed<PendingFileItem[]>(() =>
  pendingFiles.value.map((f, idx) => ({
    uid: `${idx}-${f.name}-${f.size}`,
    name: f.name,
    size: f.size,
    file: f
  }))
)

const fileColumns = [
  { title: '文件名', key: 'name', dataIndex: 'name', ellipsis: true },
  { title: '大小', key: 'size', dataIndex: 'size', width: 100 },
  { title: '操作', key: 'action', width: 80 }
]

const docColumns = [
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true, width: 220 },
  { title: '来源文件', key: 'source_file', dataIndex: 'source_file', width: 200, ellipsis: true },
  { title: '解析状态', key: 'parse_status', dataIndex: 'parse_status', width: 100 },
  { title: '创建时间', key: 'created_at', dataIndex: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const }
]

const uploadResultDesc = computed(() => {
  if (!uploadResult.value) return ''
  const r = uploadResult.value
  const parts: string[] = []
  if (r.skipped_duplicate.length > 0) {
    parts.push(`跳过重复 ${r.skipped_duplicate.length} 个`)
  }
  if (r.failed.length > 0) {
    parts.push(`失败 ${r.failed.length} 个`)
  }
  return parts.length > 0 ? parts.join('，') : '全部上传成功'
})

async function fetchKbDetail(): Promise<void> {
  kbLoading.value = true
  loadError.value = ''
  try {
    const data = await getKnowledgeBaseDetail(kbId.value)
    kb.value = data
    uploadOptions.value.parse_immediately = data.parse_on_upload
  } catch (e) {
    loadError.value = (e as Error).message || '无法加载知识库'
  } finally {
    kbLoading.value = false
  }
}

async function fetchDocuments(): Promise<void> {
  docLoading.value = true
  try {
    const res: PaginatedData<Knowledge> = await getKnowledgeBaseDocuments(kbId.value, {
      page: docQuery.value.page,
      page_size: docQuery.value.page_size,
      parse_status: docQuery.value.parse_status,
      keyword: docQuery.value.keyword || undefined
    })
    documents.value = (res.items || []) as KbDocument[]
    docPagination.value.total = res.total || 0
    docPagination.value.current = res.page || 1
  } catch {
    // ignore
  } finally {
    docLoading.value = false
  }
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

// 上传相关
function handleBeforeUpload(file: File): boolean {
  pendingFiles.value.push(file)
  return false
}

function triggerFolderSelect(): void {
  folderInputRef.value?.click()
}

function onFolderChange(e: Event): void {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    const files = Array.from(target.files).filter(
      (f) => f.size > 0 || /\.[a-z0-9]+$/i.test(f.name)
    )
    if (files.length > 0) {
      pendingFiles.value.push(...files)
      message.info(`已添加 ${files.length} 个文件`)
    }
    target.value = ''
  }
}

function removePendingFile(uid: string): void {
  const idx = pendingFileList.value.findIndex((f) => f.uid === uid)
  if (idx >= 0) {
    pendingFiles.value.splice(idx, 1)
  }
}

function clearPendingFiles(): void {
  pendingFiles.value = []
  uploadResult.value = null
}

async function handleUpload(): Promise<void> {
  if (pendingFiles.value.length === 0) {
    message.warning('请先选择文件')
    return
  }
  uploading.value = true
  uploadResult.value = null
  try {
    const result = await uploadToKnowledgeBase(kbId.value, pendingFiles.value, {
      category_id: uploadOptions.value.category_id || undefined,
      tag_ids: uploadOptions.value.tag_ids.length > 0 ? uploadOptions.value.tag_ids : undefined,
      auto_tag: uploadOptions.value.auto_tag,
      parse_immediately: uploadOptions.value.parse_immediately
    })
    uploadResult.value = result
    const failedCount = result.failed?.length || 0
    if (failedCount === 0) {
      message.success(`上传完成：成功 ${result.created} 个文件`)
    } else {
      message.warning(`上传完成：成功 ${result.created} 个，失败 ${failedCount} 个`)
    }
    pendingFiles.value = []
    fetchDocuments()
    if (kb.value) {
      kb.value.document_count = (kb.value.document_count || 0) + result.created
    }
    showUploadModal.value = false
  } catch {
    message.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

async function onCreateTag(name: string, color?: string): Promise<void> {
  try {
    const tag = await createTag({ name, color })
    tags.value.push(tag)
    uploadOptions.value.tag_ids.push(tag.id)
    message.success(`标签「${name}」已创建`)
  } catch {
    // ignore
  }
}

// 文档操作
function onDocSearch(): void {
  docQuery.value.page = 1
  fetchDocuments()
}

function onDocTableChange(pag: { current?: number; pageSize?: number }): void {
  docQuery.value.page = pag.current || 1
  docQuery.value.page_size = pag.pageSize || 10
  docPagination.value.current = docQuery.value.page
  docPagination.value.pageSize = docQuery.value.page_size
  fetchDocuments()
}

function onSelectChange(keys: number[]): void {
  selectedRowKeys.value = keys
}

function viewDocument(kid: number): void {
  router.push(`/knowledge/detail/${kid}`)
}

async function handleParseDoc(kid: number): Promise<void> {
  parsingIds.value = [...parsingIds.value, kid]
  try {
    await parseDocument(kbId.value, kid)
    message.success('已触发解析')
    fetchDocuments()
  } catch {
    // ignore
  } finally {
    parsingIds.value = parsingIds.value.filter((id) => id !== kid)
  }
}

async function handleParseAll(): Promise<void> {
  parseAllLoading.value = true
  try {
    const res = await parseAllDocuments(kbId.value)
    if (res.failed > 0) {
      message.warning(`批量解析完成：成功 ${res.success} 个，失败 ${res.failed} 个`)
    } else {
      message.success(`批量解析完成：共处理 ${res.total} 个`)
    }
    fetchDocuments()
  } catch {
    // ignore
  } finally {
    parseAllLoading.value = false
  }
}

async function handleParseSelected(): Promise<void> {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要解析的资料')
    return
  }
  parseSelectedLoading.value = true
  let successCount = 0
  let failedCount = 0
  for (const kid of selectedRowKeys.value) {
    try {
      await parseDocument(kbId.value, kid)
      successCount++
    } catch {
      failedCount++
    }
  }
  if (failedCount > 0) {
    message.warning(`解析完成：成功 ${successCount} 个，失败 ${failedCount} 个`)
  } else {
    message.success(`解析完成：成功 ${successCount} 个`)
  }
  selectedRowKeys.value = []
  fetchDocuments()
  parseSelectedLoading.value = false
}

async function handleDeleteDoc(kid: number): Promise<void> {
  try {
    await deleteKnowledge(kid)
    message.success('删除成功')
    fetchDocuments()
    if (kb.value) {
      kb.value.document_count = Math.max(0, (kb.value.document_count || 0) - 1)
    }
  } catch {
    // ignore
  }
}

// 辅助函数
function canParse(status?: string): boolean {
  return !status || status === 'pending' || status === 'failed'
}

function parseStatusColor(status?: string): string {
  const map: Record<string, string> = {
    pending: 'orange',
    parsing: 'blue',
    parsed: 'green',
    failed: 'red'
  }
  return map[status || 'pending'] || 'default'
}

function parseStatusText(status?: string): string {
  const map: Record<string, string> = {
    pending: '待解析',
    parsing: '解析中',
    parsed: '已解析',
    failed: '解析失败'
  }
  return map[status || 'pending'] || status || '-'
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  if (route.params.id) {
    fetchKbDetail()
    fetchDocuments()
    fetchCategories()
    fetchTags()
  }
  // 设置文件夹上传支持（webkitdirectory 非标准属性，需通过 DOM 设置以避免类型错误）
  if (folderInputRef.value) {
    folderInputRef.value.setAttribute('webkitdirectory', '')
    folderInputRef.value.setAttribute('directory', '')
  }
})
</script>

<style scoped>
.kb-detail {
  max-width: 1400px;
  margin: 0 auto;
}

.page-toolbar {
  margin-bottom: 12px;
}

.info-card {
  margin-bottom: 16px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.kb-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
  color: rgba(0, 0, 0, 0.88);
}

.kb-desc {
  color: rgba(0, 0, 0, 0.65);
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.kb-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.55);
  margin-bottom: 12px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.kb-models {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.upload-card {
  margin-bottom: 16px;
}

.upload-actions {
  margin-top: 12px;
}

.upload-options {
  margin-top: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
}

.pending-files {
  margin-top: 16px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-weight: 500;
}

.file-name {
  display: flex;
  align-items: center;
  gap: 6px;
}

.upload-btn-area {
  margin-top: 16px;
}

.upload-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 8px 0;
}

.progress-text {
  color: rgba(0, 0, 0, 0.65);
  font-size: 14px;
}

.upload-result {
  margin-top: 16px;
}

.docs-card {
  margin-bottom: 16px;
}

.docs-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.text-muted {
  color: rgba(0, 0, 0, 0.35);
}

@media (max-width: 768px) {
  .docs-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
