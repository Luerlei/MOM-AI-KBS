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

  <a-modal
    v-model:open="createModalVisible"
    title="新建标签"
    :confirm-loading="creating"
    ok-text="创建"
    cancel-text="取消"
    @ok="confirmCreate"
    @cancel="createModalVisible = false"
  >
    <a-form layout="vertical">
      <a-form-item label="标签名称" required>
        <a-input
          ref="createInputRef"
          v-model:value="createTagName"
          placeholder="请输入标签名称"
          :maxlength="50"
          @press-enter="confirmCreate"
        />
      </a-form-item>
      <a-form-item label="颜色">
        <div class="color-picker">
          <div
            v-for="c in presetColors"
            :key="c.value"
            class="color-swatch"
            :class="{ 'color-active': createTagColor === c.value }"
            :style="{ background: c.value }"
            :title="c.label"
            @click="createTagColor = c.value"
          />
          <div
            class="color-swatch color-none"
            :class="{ 'color-active': !createTagColor }"
            title="无颜色"
            @click="createTagColor = ''"
          >
            <span class="color-none-text">无</span>
          </div>
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
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
  (e: 'create', name: string, color?: string): void
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

function filterOption(input: string, option: any): boolean {
  if (!input) return true
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

// 新建标签弹窗
const createModalVisible = ref(false)
const creating = ref(false)
const createTagName = ref('')
const createTagColor = ref('')
const createInputRef = ref<{ focus: () => void } | null>(null)

// 预设标准色
const presetColors = [
  { label: '蓝色', value: 'blue' },
  { label: '绿色', value: 'green' },
  { label: '红色', value: 'red' },
  { label: '橙色', value: 'orange' },
  { label: '紫色', value: 'purple' },
  { label: '青色', value: 'cyan' },
  { label: '粉色', value: 'pink' },
  { label: '金色', value: 'gold' },
  { label: '靛蓝', value: 'geekblue' },
  { label: '火山', value: 'volcano' },
]

function onCreate(): void {
  if (searchValue.value.trim()) {
    // 搜索框有内容时直接创建（无颜色）
    emit('create', searchValue.value.trim())
    searchValue.value = ''
  } else {
    // 搜索框为空时弹出输入弹窗
    createTagName.value = ''
    createTagColor.value = ''
    createModalVisible.value = true
    nextTick(() => {
      createInputRef.value?.focus()
    })
  }
}

function confirmCreate(): void {
  const name = createTagName.value.trim()
  if (!name) {
    message.warning('请输入标签名称')
    return
  }
  emit('create', name, createTagColor.value || undefined)
  createModalVisible.value = false
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

.color-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.color-swatch:hover {
  transform: scale(1.15);
}

.color-active {
  border-color: #333;
  box-shadow: 0 0 0 2px #fff inset;
}

.color-none {
  background: #fafafa;
  border: 1px solid #d9d9d9;
}

.color-none-text {
  font-size: 11px;
  color: #999;
}
</style>
