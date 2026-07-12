<template>
  <div class="skill-list">
    <a-row :gutter="16">
      <!-- 左侧筛选 -->
      <a-col :xs="24" :md="6" :lg="5">
        <a-card title="筛选" size="small">
          <!-- 模块维度 -->
          <div class="filter-section">
            <div class="section-title-row">
              <span class="section-title">模块维度</span>
              <a-button type="link" size="small" @click="categoryManagerVisible = true">
                管理
              </a-button>
            </div>
            <a-radio-group
              v-model:value="filter.category"
              button-style="solid"
              style="display: flex; flex-direction: column; gap: 4px"
              @change="onFilterChange"
            >
              <a-radio-button
                v-for="opt in categoryOptions"
                :key="opt.value"
                :value="opt.value"
                style="width: 100%; text-align: left; margin-left: 0"
              >
                {{ opt.label }}
              </a-radio-button>
            </a-radio-group>
          </div>
          <a-divider style="margin: 12px 0" />
          <!-- 功能维度 -->
          <div class="filter-section">
            <div class="section-title-row">
              <span class="section-title">功能维度</span>
              <a-button type="link" size="small" @click="functionManagerVisible = true">
                管理
              </a-button>
            </div>
            <a-radio-group
              v-model:value="filter.function"
              button-style="solid"
              style="display: flex; flex-direction: column; gap: 4px"
              @change="onFilterChange"
            >
              <a-radio-button
                v-for="opt in functionOptions"
                :key="opt.value"
                :value="opt.value"
                style="width: 100%; text-align: left; margin-left: 0"
              >
                {{ opt.label }}
              </a-radio-button>
            </a-radio-group>
          </div>
          <a-divider style="margin: 12px 0" />
          <!-- 状态 -->
          <div class="filter-section">
            <div class="section-title-row">
              <span class="section-title">状态</span>
            </div>
            <a-radio-group
              v-model:value="filter.enabled"
              button-style="solid"
              style="display: flex; gap: 4px"
              @change="onFilterChange"
            >
              <a-radio-button :value="undefined">全部</a-radio-button>
              <a-radio-button :value="true">已启用</a-radio-button>
              <a-radio-button :value="false">已禁用</a-radio-button>
            </a-radio-group>
          </div>
        </a-card>
      </a-col>

      <!-- 右侧表格 -->
      <a-col :xs="24" :md="18" :lg="19">
        <a-card :body-style="{ padding: 0 }">
          <div class="toolbar">
            <span class="title-text">Skill 列表</span>
            <a-space>
              <a-button @click="showTemplateModal = true">
                <CopyOutlined />从模板创建
              </a-button>
              <a-button type="primary" @click="goCreate">
                <PlusOutlined />新建 Skill
              </a-button>
            </a-space>
          </div>
          <a-table
            :columns="columns"
            :data-source="tableData"
            :loading="loading"
            row-key="id"
            size="middle"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <span class="skill-name">{{ record.name }}</span>
                <div class="skill-desc">{{ record.description }}</div>
              </template>
              <template v-else-if="column.key === 'category'">
                <a-tag :color="categoryColor(record.category)">
                  {{ record.category }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'function'">
                <a-tag :color="functionColor(record.function)">
                  {{ record.function }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'enabled'">
                <a-switch
                  :checked="record.enabled"
                  @change="onToggle(record)"
                  :loading="record._toggling"
                />
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openTestModal(record)">
                    测试
                  </a-button>
                  <a-button type="link" size="small" @click="goEdit(record.id)">编辑</a-button>
                  <a-popconfirm title="确定删除该 Skill?" @confirm="handleDelete(record.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <!-- 测试弹窗 -->
    <a-modal
      v-model:open="testVisible"
      title="Skill 路由测试"
      @ok="runTest"
      :confirm-loading="testLoading"
      width="600px"
    >
      <a-form layout="vertical">
        <a-form-item label="测试问题">
          <a-input
            v-model:value="testQuestion"
            placeholder="输入用于测试路由匹配的问题"
          />
        </a-form-item>
      </a-form>
      <div v-if="testResult" class="test-result">
        <a-divider />
        <a-alert
          :message="testResult.match_type !== 'default' ? '匹配成功' : '未匹配（使用默认 Skill）'"
          :type="testResult.match_type !== 'default' ? 'success' : 'warning'"
          show-icon
        >
          <template #description>
            <div>
              <div>匹配 Skill：{{ testResult.matched_skill?.name || '未知' }}</div>
              <div>匹配方式：{{ matchTypeLabel(testResult.match_type) }}</div>
              <div v-if="testResult.score > 0">得分：{{ testResult.score.toFixed(3) }}</div>
            </div>
          </template>
        </a-alert>
        <a-table
          v-if="testResult.all_scores && testResult.all_scores.length > 0"
          :data-source="testResult.all_scores"
          :columns="testScoreColumns"
          :pagination="false"
          size="small"
          row-key="skill_id"
          style="margin-top: 12px"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'skill_name'">
              <span :style="{ fontWeight: record.skill_id === testResult.matched_skill?.id ? 'bold' : 'normal' }">
                {{ record.skill_name }}
              </span>
            </template>
          </template>
        </a-table>
      </div>
    </a-modal>

    <!-- 模板选择弹窗 -->
    <a-modal
      v-model:open="showTemplateModal"
      title="从模板创建 Skill"
      @ok="createFromTemplate"
      :confirm-loading="templateLoading"
      width="640px"
    >
      <a-list
        :data-source="templates"
        :loading="templateListLoading"
        item-layout="horizontal"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-radio
              :checked="selectedTemplateId === item.id"
              @click="selectedTemplateId = item.id"
            >
              <a-list-item-meta>
                <template #title>{{ item.name }}</template>
                <template #description>{{ item.description }}</template>
              </a-list-item-meta>
            </a-radio>
          </a-list-item>
        </template>
      </a-list>
    </a-modal>

    <!-- 模块分类管理 -->
    <SkillOptionManager
      v-model="categoryManagerVisible"
      type="category"
      @refresh="loadCategoryOptions"
    />
    <!-- 功能分类管理 -->
    <SkillOptionManager
      v-model="functionManagerVisible"
      type="function"
      @refresh="loadFunctionOptions"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PlusOutlined, CopyOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import {
  getSkillList,
  deleteSkill,
  toggleSkill,
  testSkill,
  getSkillTemplates,
  createSkillFromTemplate
} from '@/api/skill'
import { getSkillOptions } from '@/api/skillOption'
import SkillOptionManager from '@/components/SkillOptionManager.vue'
import type { Skill, SkillOption, SkillTestResult, SkillTemplate } from '@/types'

const router = useRouter()

const loading = ref(false)
const tableData = ref<(Skill & { _toggling?: boolean })[]>([])

const filter = ref<{
  category?: string
  function?: string
  enabled?: boolean
}>({
  category: undefined,
  function: undefined,
  enabled: undefined
})

const columns = [
  { title: '名称', key: 'name', dataIndex: 'name', ellipsis: true },
  { title: '模块', key: 'category', dataIndex: 'category', width: 120 },
  { title: '功能', key: 'function', dataIndex: 'function', width: 100 },
  { title: '状态', key: 'enabled', dataIndex: 'enabled', width: 90 },
  { title: '操作', key: 'action', width: 220, fixed: 'right' as const }
]

// 分类/功能选项（从后端动态加载）
const categoryList = ref<SkillOption[]>([])
const functionList = ref<SkillOption[]>([])

const categoryOptions = computed(() => [
  { label: '全部', value: undefined },
  ...categoryList.value.map((c) => ({ label: c.name, value: c.name }))
])

const functionOptions = computed(() => [
  { label: '全部', value: undefined },
  ...functionList.value.map((f) => ({ label: f.name, value: f.name }))
])

// 分类/功能管理弹窗
const categoryManagerVisible = ref(false)
const functionManagerVisible = ref(false)

// 颜色查找：返回选项配置的 color
function categoryColor(name: string): string {
  const opt = categoryList.value.find((c) => c.name === name)
  return opt?.color || 'default'
}

function functionColor(name: string): string {
  const opt = functionList.value.find((f) => f.name === name)
  return opt?.color || 'default'
}

async function loadCategoryOptions(): Promise<void> {
  try {
    categoryList.value = await getSkillOptions('category')
  } catch {
    categoryList.value = []
  }
}

async function loadFunctionOptions(): Promise<void> {
  try {
    functionList.value = await getSkillOptions('function')
  } catch {
    functionList.value = []
  }
}

function onFilterChange(): void {
  fetchData()
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const data = await getSkillList({
      category: filter.value.category,
      function: filter.value.function,
      enabled: filter.value.enabled
    })
    tableData.value = data || []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

function goCreate(): void {
  router.push('/skills/edit')
}

function goEdit(id: number): void {
  router.push(`/skills/edit/${id}`)
}

async function onToggle(record: Skill & { _toggling?: boolean }): Promise<void> {
  record._toggling = true
  try {
    await toggleSkill(record.id)
    record.enabled = !record.enabled
    message.success(`已${record.enabled ? '启用' : '禁用'}`)
  } catch {
    // ignore
  } finally {
    record._toggling = false
  }
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteSkill(id)
    message.success('删除成功')
    fetchData()
  } catch {
    // ignore
  }
}

// 测试
const testVisible = ref(false)
const testQuestion = ref('')
const testLoading = ref(false)
const testResult = ref<SkillTestResult | null>(null)
const currentSkillId = ref<number | null>(null)

const testScoreColumns = [
  { title: 'Skill', dataIndex: 'skill_name', key: 'skill_name' },
  { title: '关键词命中', dataIndex: 'keyword_hits', key: 'keyword_hits', width: 100 },
  { title: '语义得分', dataIndex: 'semantic_score', key: 'semantic_score', width: 100,
    customRender: ({ text }: { text: number }) => text > 0 ? text.toFixed(3) : '-' },
]

function matchTypeLabel(type: string): string {
  switch (type) {
    case 'keyword': return '关键词匹配'
    case 'semantic': return '语义匹配'
    case 'default': return '默认兜底'
    default: return type
  }
}

function openTestModal(record: Skill): void {
  currentSkillId.value = record.id
  testQuestion.value = ''
  testResult.value = null
  testVisible.value = true
}

async function runTest(): Promise<void> {
  if (!currentSkillId.value || !testQuestion.value.trim()) {
    message.warning('请输入测试问题')
    return
  }
  testLoading.value = true
  try {
    testResult.value = await testSkill(currentSkillId.value, testQuestion.value)
  } catch {
    testResult.value = null
  } finally {
    testLoading.value = false
  }
}

// 模板
const showTemplateModal = ref(false)
const templateLoading = ref(false)
const templateListLoading = ref(false)
const templates = ref<SkillTemplate[]>([])
const selectedTemplateId = ref<string>('')

async function loadTemplates(): Promise<void> {
  templateListLoading.value = true
  try {
    templates.value = await getSkillTemplates()
  } catch {
    templates.value = []
  } finally {
    templateListLoading.value = false
  }
}

async function createFromTemplate(): Promise<void> {
  if (!selectedTemplateId.value) {
    message.warning('请选择模板')
    return
  }
  templateLoading.value = true
  try {
    const skill = await createSkillFromTemplate(selectedTemplateId.value)
    message.success('从模板创建成功')
    showTemplateModal.value = false
    router.push(`/skills/edit/${skill.id}`)
  } catch {
    // ignore
  } finally {
    templateLoading.value = false
  }
}

onMounted(() => {
  fetchData()
  loadTemplates()
  loadCategoryOptions()
  loadFunctionOptions()
})
</script>

<style scoped>
.skill-list {
  min-height: 400px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section-title {
  font-weight: 600;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
}

.title-text {
  font-size: 16px;
  font-weight: 600;
}

.skill-name {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}

.skill-desc {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}

.test-result {
  margin-top: 16px;
}
</style>
