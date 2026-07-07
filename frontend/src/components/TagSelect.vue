<template>
  <a-select
    :value="selectedTagIds"
    mode="multiple"
    show-search
    :placeholder="placeholder"
    :token-separators="[',']"
    :loading="loading"
    :allow-clear="true"
    :filter-option="filterOption"
    :style="{ width: width }"
    @change="onChange"
    @search="onSearch"
  >
    <a-select-option v-for="tag in tags" :key="tag.id" :value="tag.id">
      <a-tag :color="tag.color || 'default'">{{ tag.name }}</a-tag>
    </a-select-option>
    <template #dropdownRender="menu">
      <component :is="menu" />
      <a-divider style="margin: 4px 0" />
      <div class="create-tag" @mousedown.prevent="onCreate">
        <PlusOutlined /> {{ searchValue ? `新建「${searchValue}」标签` : '新建标签' }}
      </div>
    </template>
  </a-select>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { Modal } from 'ant-design-vue'
import type { Tag } from '@/types'

const props = withDefaults(
  defineProps<{
    tags: Tag[]
    modelValue: number[]
    placeholder?: string
    width?: string
    loading?: boolean
    allowCreate?: boolean
  }>(),
  {
    placeholder: '请选择标签',
    width: '100%',
    loading: false,
    allowCreate: true
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: number[]): void
  (e: 'create', name: string): void
}>()

const searchValue = ref('')

const selectedTagIds = ref<number[]>([...props.modelValue])

import { watch } from 'vue'
watch(
  () => props.modelValue,
  (val) => {
    selectedTagIds.value = [...val]
  }
)

function filterOption(input: string, option: { value: number }): boolean {
  const tag = props.tags.find((t) => t.id === option.value)
  return tag ? tag.name.toLowerCase().includes(input.toLowerCase()) : false
}

function onChange(value: (string | number)[]): void {
  const ids = value.map((v) => Number(v))
  selectedTagIds.value = ids
  emit('update:modelValue', ids)
}

function onSearch(value: string): void {
  searchValue.value = value
}

function onCreate(): void {
  if (searchValue.value.trim()) {
    emit('create', searchValue.value.trim())
    searchValue.value = ''
  } else {
    Modal.confirm({
      title: '新建标签',
      content: '请输入标签名称：',
      okText: '创建',
      cancelText: '取消',
      onOk: () => {
        // 用户需要在搜索框中输入名称后再点击
      }
    })
  }
}
</script>

<style scoped>
.create-tag {
  padding: 8px 12px;
  cursor: pointer;
  color: #1677ff;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.create-tag:hover {
  background: #f0f5ff;
}
</style>
