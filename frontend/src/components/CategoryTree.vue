<template>
  <div class="category-tree">
    <div v-if="loading" class="loading">
      <a-spin size="small" />
    </div>
    <a-tree
      v-else
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
        </span>
      </template>
    </a-tree>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Category } from '@/types'

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
</script>

<style scoped>
.category-tree {
  min-height: 60px;
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
</style>
