<template>
  <a-modal
    :open="modelValue"
    :title="title"
    :footer="null"
    width="560px"
    @update:open="(v: boolean) => emit('update:modelValue', v)"
  >
    <!-- 新增表单 -->
    <div class="add-form">
      <a-input-group compact>
        <a-input
          v-model:value="newName"
          placeholder="输入名称"
          style="width: calc(100% - 120px)"
          @press-enter="handleAdd"
        />
        <a-select v-model:value="newColor" style="width: 120px">
          <a-select-option v-for="c in colorOptions" :key="c.value" :value="c.value">
            <a-tag :color="c.value">{{ c.label }}</a-tag>
          </a-select-option>
        </a-select>
      </a-input-group>
      <a-input
        v-model:value="newDesc"
        placeholder="描述（可选）"
        style="margin-top: 8px"
        @press-enter="handleAdd"
      />
      <a-button
        type="primary"
        :loading="addLoading"
        :disabled="!newName.trim()"
        style="margin-top: 8px"
        @click="handleAdd"
      >
        添加
      </a-button>
    </div>

    <a-divider style="margin: 12px 0" />

    <!-- 列表 -->
    <a-list
      :data-source="options"
      :loading="listLoading"
      item-layout="horizontal"
      size="small"
    >
      <template #renderItem="{ item }">
        <a-list-item>
          <div class="item-content">
            <template v-if="editingId === item.id">
              <div class="edit-row">
                <a-input v-model:value="editForm.name" placeholder="名称" />
                <a-select v-model:value="editForm.color" style="width: 100%; margin-top: 8px">
                  <a-select-option v-for="c in colorOptions" :key="c.value" :value="c.value">
                    <a-tag :color="c.value">{{ c.label }}</a-tag>
                  </a-select-option>
                </a-select>
                <a-input
                  v-model:value="editForm.description"
                  placeholder="描述"
                  style="margin-top: 8px"
                />
                <a-space style="margin-top: 8px">
                  <a-button
                    type="primary"
                    size="small"
                    :loading="editLoading"
                    @click="handleEditSave"
                  >
                    保存
                  </a-button>
                  <a-button size="small" @click="cancelEdit">取消</a-button>
                </a-space>
              </div>
            </template>
            <template v-else>
              <div class="display-row">
                <a-tag :color="item.color || 'default'">{{ item.name }}</a-tag>
                <span class="item-desc">{{ item.description || '无描述' }}</span>
                <a-space class="item-actions">
                  <a-button type="link" size="small" @click="startEdit(item)">编辑</a-button>
                  <a-popconfirm title="确定删除该选项?" @confirm="handleDelete(item.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </div>
            </template>
          </div>
        </a-list-item>
      </template>
      <template #emptyText>暂无数据</template>
    </a-list>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  getSkillOptions,
  createSkillOption,
  updateSkillOption,
  deleteSkillOption
} from '@/api/skillOption'
import type { SkillOption } from '@/types'

const props = defineProps<{
  type: 'category' | 'function'
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
}>()

const colorOptions = [
  { label: '默认', value: 'default' },
  { label: '蓝色', value: 'blue' },
  { label: '青色', value: 'cyan' },
  { label: '绿色', value: 'green' },
  { label: '橙色', value: 'orange' },
  { label: '红色', value: 'red' },
  { label: '紫色', value: 'purple' }
]

const title = computed(() =>
  props.type === 'category' ? '管理模块分类' : '管理功能分类'
)

const options = ref<SkillOption[]>([])
const listLoading = ref(false)

// 新增表单
const newName = ref('')
const newColor = ref('blue')
const newDesc = ref('')
const addLoading = ref(false)

// 编辑
const editingId = ref<number | null>(null)
const editForm = ref<{ name: string; color: string; description: string }>({
  name: '',
  color: 'default',
  description: ''
})
const editLoading = ref(false)

async function loadOptions(): Promise<void> {
  listLoading.value = true
  try {
    options.value = await getSkillOptions(props.type)
  } catch {
    options.value = []
  } finally {
    listLoading.value = false
  }
}

async function handleAdd(): Promise<void> {
  if (!newName.value.trim()) {
    message.warning('请输入名称')
    return
  }
  addLoading.value = true
  try {
    await createSkillOption({
      type: props.type,
      name: newName.value.trim(),
      color: newColor.value,
      description: newDesc.value.trim() || undefined
    })
    message.success('添加成功')
    newName.value = ''
    newDesc.value = ''
    newColor.value = 'blue'
    await loadOptions()
    emit('refresh')
  } catch {
    // ignore
  } finally {
    addLoading.value = false
  }
}

function startEdit(item: SkillOption): void {
  editingId.value = item.id
  editForm.value = {
    name: item.name,
    color: item.color || 'default',
    description: item.description || ''
  }
}

function cancelEdit(): void {
  editingId.value = null
}

async function handleEditSave(): Promise<void> {
  if (editingId.value === null) return
  if (!editForm.value.name.trim()) {
    message.warning('请输入名称')
    return
  }
  editLoading.value = true
  try {
    await updateSkillOption(editingId.value, {
      name: editForm.value.name.trim(),
      color: editForm.value.color,
      description: editForm.value.description.trim()
    })
    message.success('保存成功')
    editingId.value = null
    await loadOptions()
    emit('refresh')
  } catch {
    // ignore
  } finally {
    editLoading.value = false
  }
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteSkillOption(id)
    message.success('删除成功')
    await loadOptions()
    emit('refresh')
  } catch {
    // ignore
  }
}

// 弹窗打开时加载选项
watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      loadOptions()
    } else {
      editingId.value = null
    }
  }
)
</script>

<style scoped>
.add-form {
  margin-bottom: 4px;
}

.item-content {
  width: 100%;
}

.display-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.item-desc {
  flex: 1;
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}

.item-actions {
  margin-left: auto;
}

.edit-row {
  width: 100%;
}
</style>
