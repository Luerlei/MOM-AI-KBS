<template>
  <div class="skill-edit">
    <div class="breadcrumb-bar">
      <a-breadcrumb>
        <a-breadcrumb-item>
          <router-link to="/">首页</router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>
          <router-link to="/skills">Skill管理</router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>{{ isEdit ? '编辑' : '新建' }}</a-breadcrumb-item>
      </a-breadcrumb>
    </div>
    <a-card>
      <template #title>
        <span>{{ isEdit ? '编辑 Skill' : '新建 Skill' }}</span>
      </template>
      <template #extra>
        <a-button @click="$router.back()">返回</a-button>
      </template>

      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-form-item label="名称" name="name">
              <a-input v-model:value="form.name" placeholder="请输入 Skill 名称" />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="描述" name="description">
              <a-input v-model:value="form.description" placeholder="简要描述 Skill 的作用" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :xs="24" :md="8">
            <a-form-item name="category">
              <template #label>
                <span>模块维度</span>
                <a-button
                  type="link"
                  size="small"
                  class="manage-link"
                  @click="categoryManagerVisible = true"
                >
                  管理分类
                </a-button>
              </template>
              <a-select v-model:value="form.category">
                <a-select-option
                  v-for="opt in categoryOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item name="function">
              <template #label>
                <span>功能维度</span>
                <a-button
                  type="link"
                  size="small"
                  class="manage-link"
                  @click="functionManagerVisible = true"
                >
                  管理分类
                </a-button>
              </template>
              <a-select v-model:value="form.function">
                <a-select-option
                  v-for="opt in functionOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="触发模式" name="trigger_mode">
              <a-select v-model:value="form.trigger_mode">
                <a-select-option value="keyword">关键词匹配</a-select-option>
                <a-select-option value="regex">正则匹配</a-select-option>
                <a-select-option value="semantic">语义匹配</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-form-item label="触发关键词">
              <a-select
                v-model:value="form.trigger_keywords"
                mode="tags"
                placeholder="输入关键词后回车"
                :token-separators="[',']"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="触发模式（正则）">
              <a-select
                v-model:value="form.trigger_patterns"
                mode="tags"
                placeholder="输入正则表达式后回车"
                :token-separators="[',']"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-form-item label="知识范围 - 分类">
              <a-tree-select
                v-model:value="form.knowledge_categories"
                :tree-data="categoryTreeData"
                :field-names="{ label: 'name', value: 'id', children: 'children' }"
                placeholder="选择该 Skill 可访问的分类"
                multiple
                allow-clear
                tree-default-expand-all
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-form-item label="知识范围 - 标签">
              <TagSelect
                :model-value="form.knowledge_tags || []"
                :tags="tags"
                placeholder="选择该 Skill 可访问的标签"
                @update:model-value="(v: number[]) => (form.knowledge_tags = v)"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="Prompt 模板" name="prompt_template" required>
          <div class="prompt-hint">
            支持变量：
            <a-tag color="blue">{context}</a-tag>
            <a-tag color="blue">{question}</a-tag>
            <a-tag color="blue">{history}</a-tag>
          </div>
          <a-textarea
            v-model:value="form.prompt_template"
            :rows="12"
            placeholder="请输入 Prompt 模板，使用 {context} 表示检索到的上下文，{question} 表示用户问题"
            style="font-family: 'SFMono-Regular', Consolas, monospace; font-size: 13px"
          />
        </a-form-item>

        <!-- Skill 路由测试 -->
        <a-card title="Skill 路由测试" size="small" style="margin-top: 16px">
          <a-input-group compact>
            <a-input
              v-model:value="testQuestion"
              placeholder="输入问题测试该 Skill 是否被匹配"
              style="width: calc(100% - 100px)"
            />
            <a-button
              type="primary"
              style="width: 100px"
              :loading="testLoading"
              :disabled="!form.name"
              @click="runTest"
            >
              测试
            </a-button>
          </a-input-group>
          <div v-if="testResult" class="test-result">
            <a-alert
              :message="testResult.matched ? '匹配成功' : '未匹配'"
              :type="testResult.matched ? 'success' : 'warning'"
              show-icon
            >
              <template #description>
                <div v-if="testResult.matched">
                  <div>匹配 Skill：{{ testResult.skill_name || form.name }}</div>
                  <div v-if="testResult.confidence">
                    置信度：{{ (testResult.confidence * 100).toFixed(1) }}%
                  </div>
                  <div v-if="testResult.reason">{{ testResult.reason }}</div>
                </div>
                <div v-else>没有匹配到该 Skill。</div>
              </template>
            </a-alert>
          </div>
        </a-card>

        <div class="form-actions">
          <a-space>
            <a-button @click="$router.back()">取消</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">
              {{ isEdit ? '保存' : '创建' }}
            </a-button>
          </a-space>
        </div>
      </a-form>
    </a-card>

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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, type FormInstance } from 'ant-design-vue'
import TagSelect from '@/components/TagSelect.vue'
import SkillOptionManager from '@/components/SkillOptionManager.vue'
import { getSkillDetail, createSkill, updateSkill, testSkill } from '@/api/skill'
import { getCategoryTree, getTagList } from '@/api/category'
import { getSkillOptions } from '@/api/skillOption'
import type {
  Skill,
  SkillOption,
  TriggerMode,
  Category,
  Tag,
  SkillTestResult
} from '@/types'

const route = useRoute()
const router = useRouter()

const formRef = ref<FormInstance>()
const saving = ref(false)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

const form = ref<Partial<Skill>>({
  name: '',
  description: '',
  category: '通用',
  function: '通用问答',
  trigger_keywords: [],
  trigger_patterns: [],
  trigger_mode: 'keyword' as TriggerMode,
  knowledge_categories: [],
  knowledge_tags: [],
  prompt_template: '',
  enabled: true
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择模块', trigger: 'change' }],
  function: [{ required: true, message: '请选择功能', trigger: 'change' }],
  prompt_template: [{ required: true, message: '请输入 Prompt 模板', trigger: 'blur' }]
}

const isEdit = computed(() => !!route.params.id)
const categoryTreeData = computed<Category[]>(() => categories.value)

// 分类/功能选项（从后端动态加载）
const categoryList = ref<SkillOption[]>([])
const functionList = ref<SkillOption[]>([])

const categoryOptions = computed(() =>
  categoryList.value.map((c) => ({ label: c.name, value: c.name }))
)

const functionOptions = computed(() =>
  functionList.value.map((f) => ({ label: f.name, value: f.name }))
)

// 分类/功能管理弹窗
const categoryManagerVisible = ref(false)
const functionManagerVisible = ref(false)

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

// 测试
const testQuestion = ref('')
const testLoading = ref(false)
const testResult = ref<SkillTestResult | null>(null)

async function runTest(): Promise<void> {
  if (!testQuestion.value.trim()) {
    message.warning('请输入测试问题')
    return
  }
  // 编辑模式且已有 ID 时调用接口，否则本地无法测试
  if (!form.value.id) {
    message.info('请先保存 Skill 再测试路由')
    return
  }
  testLoading.value = true
  try {
    testResult.value = await testSkill(form.value.id, testQuestion.value)
  } catch {
    testResult.value = null
  } finally {
    testLoading.value = false
  }
}

async function fetchDetail(id: number): Promise<void> {
  try {
    const data = await getSkillDetail(id)
    form.value = { ...data }
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

async function handleSave(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    if (isEdit.value) {
      await updateSkill(Number(route.params.id), payload)
      message.success('保存成功')
    } else {
      const created = await createSkill(payload)
      message.success('创建成功')
      router.push(`/skills/edit/${created.id}`)
      return
    }
    router.push('/skills')
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
        name: '',
        description: '',
        category: '通用',
        function: '通用问答',
        trigger_keywords: [],
        trigger_patterns: [],
        trigger_mode: 'keyword',
        knowledge_categories: [],
        knowledge_tags: [],
        prompt_template: '',
        enabled: true
      }
    }
  }
)

onMounted(() => {
  fetchCategories()
  fetchTags()
  loadCategoryOptions()
  loadFunctionOptions()
  if (route.params.id) {
    fetchDetail(Number(route.params.id))
  }
})
</script>

<style scoped>
.skill-edit {
  max-width: 1200px;
  margin: 0 auto;
}

.prompt-hint {
  margin-bottom: 8px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  margin-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.test-result {
  margin-top: 12px;
}

.manage-link {
  padding: 0 0 0 8px;
  height: auto;
  font-size: 13px;
  vertical-align: baseline;
}
</style>
