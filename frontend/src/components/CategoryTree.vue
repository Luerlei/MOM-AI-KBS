<template>
  <div class="category-tree">
    <div v-if="loading" class="loading">
      <a-spin size="small" />
    </div>
    <template v-else>
      <div class="tree-header">
        <a-button type="link" size="small" @click="openCreateModal(null)">
          <PlusOutlined /> 新建分类
        </a-button>
      </div>
      <a-tree
        :tree-data="treeData"
        :selected-keys="selectedKeys"
        :expanded-keys="expandedKeys"
        :field-names="fieldNames"
        :show-line="showLine"
        @select="onSelect"
        @expand="onExpand"
      >
        <template #title="node">
          <span class="tree-node">
            <span class="node-name">{{ node.name }}</span>
            <a-tag v-if="node.knowledge_count !== undefined" class="count-tag" color="blue">
              {{ node.knowledge_count }}
            </a-tag>
            <a-dropdown :trigger="['click']">
              <a class="node-action" @click.stop>...</a>
              <template #overlay>
                <a-menu @click="onNodeMenuClick($event, node)">
                  <a-menu-item key="add">新建子分类</a-menu-item>
                  <a-menu-item key="edit">重命名</a-menu-item>
                  <a-menu-item key="delete">删除</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </span>
        </template>
      </a-tree>
    </template>

    <!-- 新建/编辑分类弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalMode === 'create' ? '新建分类' : '重命名分类'"
      :confirm-loading="submitting"
      ok-text="确定"
      cancel-text="取消"
      @ok="confirmSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="分类名称" required>
          <a-input
            v-model:value="formData.name"
            placeholder="请输入分类名称"
            :maxlength="50"
            @press-enter="confirmSubmit"
          />
        </a-form-item>
        <a-form-item label="描述">
          <a-input
            v-model:value="formData.description"
            placeholder="可选"
            :maxlength="200"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import type { Category } from '@/types'
import { createCategory, updateCategory, deleteCategory } from '@/api/category'

const props = withDefaults(
  defineProps<{
    categories: Category[]
    selectedId?: number | null
    loading?: boolean
    showLine?: boolean
  }>(),
  {
    selectedId: null,
    loading: false,
    showLine: true
  }
)

const emit = defineEmits<{
  (e: 'select', categoryId: number | null, category: Category | null): void
  (e: 'refresh'): void
}>()

const fieldNames = {
  title: 'name',
  key: 'id',
  children: 'children'
}

const expandedKeys = ref<(string | number)[]>([])

const selectedKeys = computed<(string | number)[]>(() => {
  return props.selectedId ? [props.selectedId] : []
})

const treeData = computed<Category[]>(() => props.categories)

// 监听 categories 变化，自动展开所有节点
watch(
  () => props.categories,
  (val) => {
    expandedKeys.value = collectKeys(val)
  },
  { immediate: true }
)

function collectKeys(list: Category[]): (string | number)[] {
  const keys: (string | number)[] = []
  const walk = (nodes: Category[]) => {
    nodes.forEach((n) => {
      keys.push(n.id)
      if (n.children && n.children.length) walk(n.children)
    })
  }
  walk(list)
  return keys
}

function onSelect(
  selectedKeys: (string | number)[],
  info: { selected: boolean; node: { name: string; id: number } }
): void {
  if (info.selected) {
    emit('select', info.node.id as number, info.node as unknown as Category)
  } else {
    emit('select', null, null)
  }
}

function onExpand(keys: (string | number)[]): void {
  expandedKeys.value = keys
}

// ===== 分类 CRUD =====
const modalVisible = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const formData = ref({ name: '', description: '' })
const editingId = ref<number | null>(null)
const parentId = ref<number | null>(null)

function openCreateModal(parent: Category | null): void {
  modalMode.value = 'create'
  editingId.value = null
  parentId.value = parent?.id ?? null
  formData.value = { name: '', description: parent?.description || '' }
  modalVisible.value = true
}

function openEditModal(node: Category): void {
  modalMode.value = 'edit'
  editingId.value = node.id
  parentId.value = node.parent_id ?? null
  formData.value = { name: node.name, description: node.description || '' }
  modalVisible.value = true
}

async function confirmSubmit(): Promise<void> {
  const name = formData.value.name.trim()
  if (!name) {
    message.warning('请输入分类名称')
    return
  }
  submitting.value = true
  try {
    if (modalMode.value === 'create') {
      await createCategory({ name, description: formData.value.description, parent_id: parentId.value })
      message.success('创建成功')
    } else if (editingId.value) {
      await updateCategory(editingId.value, { name, description: formData.value.description })
      message.success('修改成功')
    }
    modalVisible.value = false
    emit('refresh')
  } catch {
    // ignore
  } finally {
    submitting.value = false
  }
}

function onMenuClick(key: string, node: Category): void {
  if (key === 'add') {
    openCreateModal(node)
  } else if (key === 'edit') {
    openEditModal(node)
  } else if (key === 'delete') {
    Modal.confirm({
      title: '删除分类',
      content: `确定删除分类「${node.name}」吗？子分类也会被删除。`,
      okType: 'danger',
      okText: '删除',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteCategory(node.id)
          message.success('删除成功')
          emit('refresh')
        } catch {
          // ignore
        }
      }
    })
  }
}

function onNodeMenuClick(info: { key: string | number }, node: Category): void {
  onMenuClick(String(info.key), node)
}
</script>

<style scoped>
.category-tree {
  min-height: 60px;
}

.tree-header {
  margin-bottom: 8px;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}

.tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.node-name {
  font-size: 14px;
}

.count-tag {
  margin-left: 4px;
  font-size: 11px;
  line-height: 16px;
  padding: 0 4px;
}

.node-action {
  margin-left: 4px;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.45);
  cursor: pointer;
  padding: 0 2px;
}

.node-action:hover {
  color: #1677ff;
}
</style>
