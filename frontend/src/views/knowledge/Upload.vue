<template>
  <div class="knowledge-upload">
    <a-card title="批量上传知识">
      <template #extra>
        <a-button @click="$router.back()">返回</a-button>
      </template>

      <!-- 上传区域 -->
      <FileUpload
        ref="fileUploadRef"
        @change="onFilesChange"
      />

      <!-- 元数据批量设置 -->
      <div v-if="files.length > 0" class="metadata-section">
        <a-divider>上传后批量设置元数据（可选）</a-divider>
        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-form-item label="分类">
              <a-tree-select
                v-model:value="metaForm.category_id"
                :tree-data="categoryTreeData"
                :field-names="{ label: 'name', value: 'id', children: 'children' }"
                placeholder="选择分类（应用到所有上传文件）"
                allow-clear
                tree-default-expand-all
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="标签">
              <TagSelect
                v-model="metaForm.tag_ids"
                :tags="tags"
                placeholder="选择标签（应用到所有上传文件）"
                @create="onCreateTag"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row>
          <a-col :span="24">
            <a-form-item>
              <a-switch v-model:checked="metaForm.auto_tag" />
              <span class="auto-tag-label">自动打标签（AI 分析文档内容，自动匹配或新建 1-3 个标签）</span>
            </a-form-item>
          </a-col>
        </a-row>
      </div>

      <!-- 操作按钮 -->
      <div class="actions">
        <a-space>
          <a-button @click="clearFiles" :disabled="files.length === 0">清空</a-button>
          <a-button
            type="primary"
            :loading="uploading"
            :disabled="files.length === 0"
            @click="handleUpload"
          >
            <CloudUploadOutlined />开始上传 ({{ files.length }} 个文件)
          </a-button>
        </a-space>
      </div>

      <!-- 上传结果 -->
      <div v-if="uploadResult" class="upload-result">
        <a-divider>上传结果</a-divider>
        <a-alert
          :message="`上传完成：成功 ${uploadResult.success} 个，失败 ${uploadResult.failed} 个`"
          :type="uploadResult.failed > 0 ? 'warning' : 'success'"
          show-icon
        />
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { CloudUploadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import FileUpload from '@/components/FileUpload.vue'
import TagSelect from '@/components/TagSelect.vue'
import { uploadKnowledgeFiles } from '@/api/knowledge'
import { getCategoryTree, getTagList, createTag } from '@/api/category'
import type { Category, Tag } from '@/types'

const router = useRouter()

const fileUploadRef = ref<InstanceType<typeof FileUpload>>()
const files = ref<File[]>([])
const uploading = ref(false)
const uploadResult = ref<{ success: number; failed: number } | null>(null)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

const metaForm = ref({
  category_id: null as number | null,
  tag_ids: [] as number[],
  auto_tag: false
})

const categoryTreeData = computed<Category[]>(() => categories.value)

function onFilesChange(selectedFiles: File[]): void {
  files.value = selectedFiles
}

function clearFiles(): void {
  fileUploadRef.value?.clearAll()
  files.value = []
  uploadResult.value = null
}

async function handleUpload(): Promise<void> {
  if (files.value.length === 0) {
    message.warning('请先选择文件')
    return
  }
  uploading.value = true
  uploadResult.value = null
  const total = files.value.length
  try {
    const result = await uploadKnowledgeFiles(files.value, {
      category_id: metaForm.value.category_id,
      tag_ids: metaForm.value.tag_ids,
      auto_tag: metaForm.value.auto_tag
    })
    const created = Array.isArray(result) ? result : []
    uploadResult.value = {
      success: created.length || total,
      failed: total - (created.length || total)
    }
    message.success(`上传完成：${uploadResult.value.success} 个文件`)
  } catch {
    uploadResult.value = { success: 0, failed: total }
    message.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

async function onCreateTag(name: string, color?: string): Promise<void> {
  try {
    const tag = await createTag({ name, color })
    tags.value.push(tag)
    metaForm.value.tag_ids.push(tag.id)
    message.success(`标签「${name}」已创建`)
  } catch {
    // ignore
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

onMounted(() => {
  fetchCategories()
  fetchTags()
})
</script>

<style scoped>
.knowledge-upload {
  max-width: 1100px;
  margin: 0 auto;
}

.metadata-section {
  margin-top: 24px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.upload-result {
  margin-top: 16px;
}

.auto-tag-label {
  margin-left: 8px;
  color: rgba(0, 0, 0, 0.65);
}
</style>
