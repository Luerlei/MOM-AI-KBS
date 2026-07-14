<template>
  <div class="kb-list">
    <!-- 顶部工具栏 -->
    <div class="page-toolbar">
      <div class="toolbar-left">
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索知识库名称或描述"
          style="width: 320px"
          allow-clear
          @search="onSearch"
        />
      </div>
      <div class="toolbar-right">
        <a-button type="primary" @click="openCreateModal">
          <PlusOutlined />新建知识库
        </a-button>
      </div>
    </div>

    <!-- 卡片列表 -->
    <a-spin :spinning="loading">
      <a-empty
        v-if="!loading && dataList.length === 0"
        description="暂无知识库，点击右上角新建"
      />
      <a-row v-else :gutter="[16, 16]">
        <a-col v-for="kb in dataList" :key="kb.id" :xs="24" :sm="12" :lg="8">
          <a-card hoverable class="kb-card">
            <!-- 标题 -->
            <div class="card-header">
              <span class="kb-name" @click="goDetail(kb.id)">{{ kb.name }}</span>
            </div>
            <!-- 描述 -->
            <div class="kb-desc">{{ kb.description || '暂无描述' }}</div>
            <!-- 统计 -->
            <div class="kb-stats">
              <FileTextOutlined />
              <span>{{ kb.document_count || 0 }} 份资料</span>
              <a-divider type="vertical" />
              <span v-if="kb.parse_on_upload" class="auto-parse-flag">上传自动解析</span>
              <span v-else class="auto-parse-flag muted">上传不解析</span>
            </div>
            <!-- 模型配置 -->
            <div class="kb-models">
              <template v-if="hasAnyModel(kb)">
                <a-tag v-if="kb.llm_config_id" color="blue">LLM</a-tag>
                <a-tag v-if="kb.embedding_config_id" color="purple">Embedding</a-tag>
                <a-tag v-if="kb.rerank_config_id" color="cyan">Rerank</a-tag>
                <a-tag v-if="kb.ocr_config_id" color="orange">OCR</a-tag>
                <a-tag v-if="kb.vlm_config_id" color="magenta">VLM</a-tag>
              </template>
              <span v-else class="inherit-text">全部继承全局配置</span>
            </div>
            <!-- 底部 -->
            <div class="card-footer">
              <span class="kb-time">{{ formatTime(kb.created_at) }}</span>
              <a-space>
                <a-button type="link" size="small" @click="goDetail(kb.id)">进入详情</a-button>
                <a-button type="link" size="small" @click="openEditModal(kb)">编辑</a-button>
                <a-popconfirm
                  title="确定删除此知识库？相关资料将一并删除，此操作不可恢复。"
                  ok-text="删除"
                  ok-type="danger"
                  @confirm="handleDelete(kb.id)"
                >
                  <a-button type="link" size="small" danger>删除</a-button>
                </a-popconfirm>
              </a-space>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>

    <!-- 分页 -->
    <div v-if="pagination.total > 0" class="pagination-wrap">
      <a-pagination
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        show-size-changer
        :show-total="(total: number) => `共 ${total} 个知识库`"
        @change="onPageChange"
      />
    </div>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="formVisible"
      :title="editingId ? '编辑知识库' : '新建知识库'"
      :confirm-loading="submitting"
      width="640px"
      @ok="handleSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input
            v-model:value="form.name"
            placeholder="请输入知识库名称"
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
        <a-divider orientation="left" style="font-size: 13px; margin: 8px 0">
          模型配置
        </a-divider>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="LLM 模型">
              <a-select
                v-model:value="form.llm_config_id"
                :loading="modelLoading"
                placeholder="继承全局"
              >
                <a-select-option :value="null">继承全局</a-select-option>
                <a-select-option
                  v-for="m in modelsByType('LLM')"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} ({{ m.model_name }})
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Embedding 模型">
              <a-select
                v-model:value="form.embedding_config_id"
                :loading="modelLoading"
                placeholder="继承全局"
              >
                <a-select-option :value="null">继承全局</a-select-option>
                <a-select-option
                  v-for="m in modelsByType('Embedding')"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} ({{ m.model_name }})
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Rerank 模型">
              <a-select
                v-model:value="form.rerank_config_id"
                :loading="modelLoading"
                placeholder="继承全局"
              >
                <a-select-option :value="null">继承全局</a-select-option>
                <a-select-option
                  v-for="m in modelsByType('Rerank')"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} ({{ m.model_name }})
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="OCR 模型">
              <a-select
                v-model:value="form.ocr_config_id"
                :loading="modelLoading"
                placeholder="继承全局"
              >
                <a-select-option :value="null">继承全局</a-select-option>
                <a-select-option
                  v-for="m in modelsByType('OCR')"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} ({{ m.model_name }})
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="VLM 模型">
              <a-select
                v-model:value="form.vlm_config_id"
                :loading="modelLoading"
                placeholder="继承全局"
              >
                <a-select-option :value="null">继承全局</a-select-option>
                <a-select-option
                  v-for="m in modelsByType('VLM')"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} ({{ m.model_name }})
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="上传时自动解析">
          <a-switch v-model:checked="form.parse_on_upload" />
          <span class="form-hint">开启后，新上传的资料将自动触发解析流程</span>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  PlusOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  getKnowledgeBaseList,
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase
} from '@/api/knowledgeBase'
import { getModelList } from '@/api/model'
import type {
  KnowledgeBase,
  KnowledgeBaseForm,
  PaginatedData,
  ModelConfig,
  ModelType
} from '@/types'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const modelLoading = ref(false)
const dataList = ref<KnowledgeBase[]>([])
const modelList = ref<ModelConfig[]>([])

const query = ref({
  keyword: '',
  page: 1,
  page_size: 12
})

const pagination = ref({
  current: 1,
  pageSize: 12,
  total: 0
})

interface KbForm {
  name: string
  description: string
  llm_config_id: number | null
  embedding_config_id: number | null
  rerank_config_id: number | null
  ocr_config_id: number | null
  vlm_config_id: number | null
  parse_on_upload: boolean
}

function getEmptyForm(): KbForm {
  return {
    name: '',
    description: '',
    llm_config_id: null,
    embedding_config_id: null,
    rerank_config_id: null,
    ocr_config_id: null,
    vlm_config_id: null,
    parse_on_upload: true
  }
}

const formVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref<KbForm>(getEmptyForm())

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res: PaginatedData<KnowledgeBase> = await getKnowledgeBaseList({
      keyword: query.value.keyword || undefined,
      page: query.value.page,
      page_size: query.value.page_size
    })
    dataList.value = res.items || []
    pagination.value.total = res.total || 0
    pagination.value.current = res.page || 1
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchModels(): Promise<void> {
  modelLoading.value = true
  try {
    modelList.value = await getModelList()
  } catch {
    modelList.value = []
  } finally {
    modelLoading.value = false
  }
}

function modelsByType(type: ModelType): ModelConfig[] {
  return modelList.value.filter((m) => m.type === type && m.is_active)
}

function onSearch(): void {
  query.value.page = 1
  fetchData()
}

function onPageChange(page: number, pageSize: number): void {
  query.value.page = page
  query.value.page_size = pageSize
  fetchData()
}

function goDetail(id: number): void {
  router.push(`/knowledge-base/detail/${id}`)
}

function openCreateModal(): void {
  editingId.value = null
  form.value = getEmptyForm()
  formVisible.value = true
  if (modelList.value.length === 0) {
    fetchModels()
  }
}

function openEditModal(kb: KnowledgeBase): void {
  editingId.value = kb.id
  form.value = {
    name: kb.name,
    description: kb.description || '',
    llm_config_id: kb.llm_config_id,
    embedding_config_id: kb.embedding_config_id,
    rerank_config_id: kb.rerank_config_id,
    ocr_config_id: kb.ocr_config_id,
    vlm_config_id: kb.vlm_config_id,
    parse_on_upload: kb.parse_on_upload
  }
  formVisible.value = true
  if (modelList.value.length === 0) {
    fetchModels()
  }
}

async function handleSubmit(): Promise<void> {
  if (!form.value.name.trim()) {
    message.warning('请输入知识库名称')
    return
  }
  submitting.value = true
  try {
    const payload: KnowledgeBaseForm = {
      name: form.value.name.trim(),
      description: form.value.description?.trim() || undefined,
      llm_config_id: form.value.llm_config_id,
      embedding_config_id: form.value.embedding_config_id,
      rerank_config_id: form.value.rerank_config_id,
      ocr_config_id: form.value.ocr_config_id,
      vlm_config_id: form.value.vlm_config_id,
      parse_on_upload: form.value.parse_on_upload
    }
    if (editingId.value) {
      await updateKnowledgeBase(editingId.value, payload)
      message.success('更新成功')
    } else {
      await createKnowledgeBase(payload)
      message.success('创建成功')
    }
    formVisible.value = false
    fetchData()
  } catch {
    // ignore
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteKnowledgeBase(id)
    message.success('删除成功')
    fetchData()
  } catch {
    // ignore
  }
}

function hasAnyModel(kb: KnowledgeBase): boolean {
  return !!(
    kb.llm_config_id ||
    kb.embedding_config_id ||
    kb.rerank_config_id ||
    kb.ocr_config_id ||
    kb.vlm_config_id
  )
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.kb-list {
  min-height: 400px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kb-card {
  height: 100%;
  transition: box-shadow 0.2s, transform 0.2s;
}

.kb-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kb-name {
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-name:hover {
  color: #1677ff;
}

.kb-desc {
  color: rgba(0, 0, 0, 0.65);
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 42px;
}

.kb-stats {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.55);
  margin-bottom: 12px;
}

.auto-parse-flag {
  color: #1677ff;
  font-size: 12px;
}

.auto-parse-flag.muted {
  color: rgba(0, 0, 0, 0.35);
}

.kb-models {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
  min-height: 24px;
}

.inherit-text {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.35);
  font-style: italic;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.kb-time {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.4);
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.form-hint {
  margin-left: 8px;
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}

@media (max-width: 768px) {
  .page-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
