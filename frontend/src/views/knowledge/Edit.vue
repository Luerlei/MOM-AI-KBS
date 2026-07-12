<template>
  <div class="knowledge-edit">
    <a-card>
      <template #title>
        <span>{{ isEdit ? '编辑知识' : '新建知识' }}</span>
      </template>
      <template #extra>
        <a-space>
          <a-button @click="$router.back()">返回</a-button>
          <a-button @click="$router.back()">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">
            {{ isEdit ? '保存修改' : '创建' }}
          </a-button>
        </a-space>
      </template>

      <a-form
        ref="formRef"
        :model="form"
        :rules="rules"
        layout="vertical"
      >
        <a-row :gutter="16">
          <a-col :xs="24" :md="16">
            <a-form-item label="标题" name="title">
              <a-input
                v-model:value="form.title"
                placeholder="请输入标题"
                :maxlength="200"
                show-count
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="内容类型" name="content_type">
              <a-select v-model:value="form.content_type">
                <a-select-option value="markdown">Markdown</a-select-option>
                <a-select-option value="text">纯文本</a-select-option>
                <a-select-option value="html">HTML</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-form-item label="分类" name="category_id">
              <a-tree-select
                v-model:value="form.category_id"
                :tree-data="categoryTreeData"
                :field-names="{ label: 'name', value: 'id', children: 'children' }"
                placeholder="请选择分类"
                allow-clear
                tree-default-expand-all
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="标签" name="tag_ids">
              <TagSelect
                v-model="form.tag_ids"
                :tags="tags"
                placeholder="选择或创建标签"
                @create="onCreateTag"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="内容" name="content" required>
          <MarkdownEditor
            v-if="form.content_type === 'markdown'"
            v-model="form.content"
          />
          <a-textarea
            v-else
            v-model:value="form.content"
            :rows="16"
            :placeholder="form.content_type === 'html' ? '请输入 HTML 内容' : '请输入内容'"
          />
        </a-form-item>

        <a-card v-if="isEdit && documents.length > 0" title="原始附件" size="small" style="margin-bottom: 16px">
          <a-list :data-source="documents" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta :title="item.filename">
                  <template #description>
                    <span>{{ item.file_type?.toUpperCase() }} · {{ formatFileSize(item.file_size) }}</span>
                  </template>
                </a-list-item-meta>
                <template #actions>
                  <a-button type="link" size="small" @click="handleDownload(item)">
                    下载
                  </a-button>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>

      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, type FormInstance } from 'ant-design-vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import TagSelect from '@/components/TagSelect.vue'
import {
  getKnowledgeDetail,
  createKnowledge,
  updateKnowledge,
  getDownloadUrl
} from '@/api/knowledge'
import { getCategoryTree, getTagList, createTag } from '@/api/category'
import type { KnowledgeForm, Category, Tag, ContentType, KnowledgeDocument } from '@/types'

const route = useRoute()
const router = useRouter()

const formRef = ref<FormInstance>()
const saving = ref(false)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const documents = ref<KnowledgeDocument[]>([])

const form = ref<KnowledgeForm>({
  title: '',
  content: '',
  content_type: 'markdown',
  category_id: null,
  tag_ids: []
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }]
}

const isEdit = computed(() => !!route.params.id)
const categoryTreeData = computed<Category[]>(() => categories.value)

async function fetchDetail(id: number): Promise<void> {
  try {
    const data = await getKnowledgeDetail(id)
    form.value = {
      title: data.title,
      content: data.content,
      content_type: data.content_type,
      category_id: data.category_id,
      tag_ids: data.tag_ids || []
    }
    documents.value = data.documents || []
  } catch {
    // ignore
  }
}

function handleDownload(doc: KnowledgeDocument): void {
  const kid = Number(route.params.id)
  const url = getDownloadUrl(kid, doc.id)
  window.open(url, '_blank')
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
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

async function onCreateTag(name: string, color?: string): Promise<void> {
  try {
    const tag = await createTag({ name, color })
    tags.value.push(tag)
    form.value.tag_ids.push(tag.id)
    message.success(`标签「${name}」已创建`)
  } catch {
    // ignore
  }
}

async function handleSave(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload: KnowledgeForm = {
      title: form.value.title,
      content: form.value.content,
      content_type: form.value.content_type as ContentType,
      category_id: form.value.category_id,
      tag_ids: form.value.tag_ids
    }
    if (isEdit.value) {
      await updateKnowledge(Number(route.params.id), payload)
      message.success('保存成功')
    } else {
      await createKnowledge(payload)
      message.success('创建成功')
    }
    router.push('/knowledge')
  } catch {
    // ignore
  } finally {
    saving.value = false
  }
}

watch(
  () => route.params.id,
  (id) => {
    if (id) {
      fetchDetail(Number(id))
    } else {
      form.value = {
        title: '',
        content: '',
        content_type: 'markdown',
        category_id: null,
        tag_ids: []
      }
    }
  }
)

onMounted(() => {
  fetchCategories()
  fetchTags()
  if (route.params.id) {
    fetchDetail(Number(route.params.id))
  }
})
</script>

<style scoped>
.knowledge-edit {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
