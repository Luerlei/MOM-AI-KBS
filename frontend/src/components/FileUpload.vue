<template>
  <div class="file-upload">
    <a-upload-dragger
      :file-list="fileList"
      :multiple="true"
      :before-upload="handleBeforeUpload"
      :show-upload-list="false"
      :accept="accept"
    >
      <p class="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p class="ant-upload-text">点击或拖拽文件到此处上传</p>
      <p class="ant-upload-hint">
        支持 .md / .txt / .pdf / .doc / .docx / .html / .xlsx / .xls / .csv 等格式
      </p>
    </a-upload-dragger>

    <!-- 文件队列 -->
    <div v-if="fileList.length > 0" class="file-list">
      <div class="list-header">
        <span>文件队列 ({{ fileList.length }})</span>
        <a-button type="link" size="small" @click="clearAll">清空</a-button>
      </div>
      <a-table
        :columns="columns"
        :data-source="tableData"
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
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ getStatusText(record.status) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" danger @click="removeFile(record.uid)">
              移除
            </a-button>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { InboxOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import type { UploadFileItem } from '@/types'

const props = withDefaults(
  defineProps<{
    accept?: string
    maxSize?: number
  }>(),
  {
    accept: '.md,.txt,.pdf,.doc,.docx,.html,.xlsx,.xls,.csv',
    maxSize: 50
  }
)

const emit = defineEmits<{
  (e: 'change', files: File[]): void
}>()

const fileList = ref<UploadFileItem[]>([])

const columns = [
  { title: '文件名', key: 'name', dataIndex: 'name', ellipsis: true },
  { title: '大小', key: 'size', dataIndex: 'size', width: 100 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 100 },
  { title: '操作', key: 'action', width: 80 }
]

const tableData = computed(() => fileList.value)

function handleBeforeUpload(file: File): boolean {
  // 大小限制
  if (file.size > props.maxSize * 1024 * 1024) {
    return false
  }
  const uid = `${Date.now()}-${Math.random().toString(36).slice(2)}`
  fileList.value.push({
    uid,
    name: file.name,
    size: file.size,
    status: 'pending',
    originFileObj: file
  })
  emitChange()
  return false
}

function removeFile(uid: string): void {
  fileList.value = fileList.value.filter((f) => f.uid !== uid)
  emitChange()
}

function clearAll(): void {
  fileList.value = []
  emitChange()
}

function emitChange(): void {
  const files = fileList.value
    .map((item) => item.originFileObj)
    .filter((f): f is File => !!f)
  emit('change', files)
}

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    pending: 'default',
    uploading: 'processing',
    done: 'success',
    error: 'error'
  }
  return map[status] || 'default'
}

function getStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待上传',
    uploading: '上传中',
    done: '已完成',
    error: '失败'
  }
  return map[status] || status
}

defineExpose({
  fileList,
  clearAll
})
</script>

<style scoped>
.file-upload {
  width: 100%;
}

.file-list {
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
</style>
