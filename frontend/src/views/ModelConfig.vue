<template>
  <div class="model-config">
    <!-- LLM 模型 -->
    <a-card title="LLM 模型配置" style="margin-bottom: 16px">
      <template #extra>
        <a-button type="primary" @click="openCreateModal('LLM')">
          <PlusOutlined />新增 LLM
        </a-button>
      </template>
      <a-table
        :columns="columns"
        :data-source="llmModels"
        :loading="loading"
        row-key="id"
        :pagination="false"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="model-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'model_name'">
            <a-tag color="blue">{{ record.model_name }}</a-tag>
          </template>
          <template v-else-if="column.key === 'api_url'">
            <span class="api-url">{{ record.api_url }}</span>
          </template>
          <template v-else-if="column.key === 'price'">
            <span v-if="record.type === 'Forecast'" class="price-na">—</span>
            <span v-else-if="!record.input_price && !record.output_price" class="price-na">未设置</span>
            <span v-else class="price-cell">
              <span>入{{ record.input_price }}</span>
              <span>出{{ record.output_price }}</span>
            </span>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-switch
              :checked="record.is_active"
              :loading="record._activating"
              @change="onActivate(record)"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button
                type="link"
                size="small"
                :loading="record._testing"
                @click="onTest(record)"
              >
                测试
              </a-button>
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-popconfirm title="确定删除该模型配置?" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-empty
        v-if="!loading && llmModels.length === 0"
        description="尚未配置 LLM 模型，点击右上角新增"
      />
    </a-card>

    <!-- Embedding 模型 -->
    <a-card title="Embedding 模型配置" style="margin-bottom: 16px">
      <template #extra>
        <a-button type="primary" @click="openCreateModal('Embedding')">
          <PlusOutlined />新增 Embedding
        </a-button>
      </template>
      <a-table
        :columns="columns"
        :data-source="embeddingModels"
        :loading="loading"
        row-key="id"
        :pagination="false"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="model-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'model_name'">
            <a-tag color="purple">{{ record.model_name }}</a-tag>
          </template>
          <template v-else-if="column.key === 'api_url'">
            <span class="api-url">{{ record.api_url }}</span>
          </template>
          <template v-else-if="column.key === 'price'">
            <span v-if="record.type === 'Forecast'" class="price-na">—</span>
            <span v-else-if="!record.input_price && !record.output_price" class="price-na">未设置</span>
            <span v-else class="price-cell">
              <span>入{{ record.input_price }}</span>
              <span>出{{ record.output_price }}</span>
            </span>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-switch
              :checked="record.is_active"
              :loading="record._activating"
              @change="onActivate(record)"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button
                type="link"
                size="small"
                :loading="record._testing"
                @click="onTest(record)"
              >
                测试
              </a-button>
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-popconfirm title="确定删除该模型配置?" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-empty
        v-if="!loading && embeddingModels.length === 0"
        description="尚未配置 Embedding 模型，点击右上角新增"
      />
    </a-card>

    <!-- Forecast 时序预测模型 -->
    <a-card title="Forecast 时序预测模型配置" style="margin-bottom: 16px">
      <template #extra>
        <a-button type="primary" @click="openCreateModal('Forecast')">
          <PlusOutlined />新增 Forecast
        </a-button>
      </template>
      <a-table
        :columns="columns"
        :data-source="forecastModels"
        :loading="loading"
        row-key="id"
        :pagination="false"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="model-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'model_name'">
            <a-tag color="green">{{ record.model_name }}</a-tag>
          </template>
          <template v-else-if="column.key === 'api_url'">
            <span class="api-url">{{ record.api_url }}</span>
          </template>
          <template v-else-if="column.key === 'price'">
            <span v-if="record.type === 'Forecast'" class="price-na">—</span>
            <span v-else-if="!record.input_price && !record.output_price" class="price-na">未设置</span>
            <span v-else class="price-cell">
              <span>入{{ record.input_price }}</span>
              <span>出{{ record.output_price }}</span>
            </span>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-switch
              :checked="record.is_active"
              :loading="record._activating"
              @change="onActivate(record)"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button
                type="link"
                size="small"
                :loading="record._testing"
                @click="onTest(record)"
              >
                测试
              </a-button>
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-popconfirm title="确定删除该模型配置?" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-empty
        v-if="!loading && forecastModels.length === 0"
        description="尚未配置 Forecast 模型，点击右上角新增"
      />
    </a-card>

    <!-- 编辑/新增弹窗 -->
    <a-modal
      v-model:open="formVisible"
      :title="editingId ? '编辑模型' : '新增模型'"
      @ok="handleSave"
      :confirm-loading="saving"
      width="560px"
    >
      <a-form ref="formRef" :model="form" :rules="formRules" layout="vertical">
        <a-form-item label="名称" name="name">
          <a-input v-model:value="form.name" placeholder="例如：生产环境 LLM" />
        </a-form-item>
        <a-form-item label="类型" name="type">
          <a-radio-group v-model:value="form.type" :disabled="!!editingId">
            <a-radio value="LLM">LLM 大语言模型</a-radio>
            <a-radio value="Embedding">Embedding 向量模型</a-radio>
            <a-radio value="Forecast">Forecast 时序预测模型</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="API 地址" name="api_url">
          <a-input
            v-model:value="form.api_url"
            :placeholder="form.type === 'Forecast'
              ? '例如：http://localhost:8501（本地推理服务，暴露 /predict 端点）'
              : '例如：https://api.openai.com/v1'"
          />
        </a-form-item>
        <a-form-item label="API Key" name="api_key">
          <a-input-password
            v-model:value="form.api_key"
            :placeholder="form.type === 'Forecast'
              ? (editingId ? '留空表示不修改' : '本地部署可留空')
              : (editingId ? '留空表示不修改' : '请输入 API Key')"
          />
        </a-form-item>
        <a-form-item label="模型名称" name="model_name">
          <a-input
            v-model:value="form.model_name"
            :placeholder="form.type === 'Forecast'
              ? '例如：amazon/chronos-bolt-base / google/timesfm-2.0-200m-pytorch'
              : '例如：gpt-4 / qwen-plus'"
          />
        </a-form-item>
        <a-form-item
          v-if="form.type !== 'Forecast'"
          label="Token 单价（元/千 token）"
          name="price_group"
        >
          <a-input-group compact>
            <a-input-number
              v-model:value="form.input_price"
              :min="0"
              :step="0.001"
              :precision="4"
              style="width: calc(50% - 12px)"
              placeholder="输入单价"
            >
              <template #addonBefore>输入</template>
            </a-input-number>
            <a-input-number
              v-model:value="form.output_price"
              :min="0"
              :step="0.001"
              :precision="4"
              style="width: calc(50% - 12px); margin-left: 24px"
              placeholder="输出单价"
            >
              <template #addonBefore>输出</template>
            </a-input-number>
          </a-input-group>
          <div class="price-hint">用于 Token 统计页估算成本，留空或 0 表示不估算</div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 测试结果 -->
    <a-modal v-model:open="testResultVisible" title="测试结果" :footer="null" width="480px">
      <a-result
        v-if="testResult"
        :status="testResult.success ? 'success' : 'error'"
        :title="testResult.success ? '连通成功' : '连通失败'"
        :sub-title="testResult.message"
      >
        <template v-if="testResult.latency" #extra>
          <a-tag color="blue">延迟：{{ testResult.latency }} ms</a-tag>
        </template>
      </a-result>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message, type FormInstance } from 'ant-design-vue'
import {
  getModelList,
  createModel,
  updateModel,
  deleteModel,
  activateModel,
  testModel,
  getModelStatus
} from '@/api/model'
import { useAppStore } from '@/stores/app'
import type { ModelConfig, ModelType, ModelTestResult } from '@/types'

const appStore = useAppStore()

const loading = ref(false)
const saving = ref(false)
const modelList = ref<(ModelConfig & { _activating?: boolean; _testing?: boolean })[]>([])

const columns = [
  { title: '名称', key: 'name', dataIndex: 'name' },
  { title: '模型', key: 'model_name', dataIndex: 'model_name', width: 180 },
  { title: 'API 地址', key: 'api_url', dataIndex: 'api_url', ellipsis: true },
  { title: '单价(元/千)', key: 'price', width: 140 },
  { title: '启用', key: 'is_active', dataIndex: 'is_active', width: 80 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const }
]

const llmModels = computed(() => modelList.value.filter((m) => m.type === 'LLM'))

const embeddingModels = computed(() => modelList.value.filter((m) => m.type === 'Embedding'))

const forecastModels = computed(() => modelList.value.filter((m) => m.type === 'Forecast'))

// 表单
const formRef = ref<FormInstance>()
const formVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{
  name: string
  type: ModelType
  api_url: string
  api_key: string
  model_name: string
  input_price: number
  output_price: number
}>({
  name: '',
  type: 'LLM',
  api_url: '',
  api_key: '',
  model_name: '',
  input_price: 0,
  output_price: 0
})

const formRules = computed(() => ({
  name: [{ required: true, message: '请输入名称' }],
  type: [{ required: true, message: '请选择类型' }],
  api_url: [{ required: true, message: '请输入 API 地址' }],
  api_key: form.value.type === 'Forecast'
    ? []
    : [{ required: true, message: '请输入 API Key' }],
  model_name: [{ required: true, message: '请输入模型名称' }]
}))

// 测试
const testResultVisible = ref(false)
const testResult = ref<ModelTestResult | null>(null)

function openCreateModal(type: ModelType): void {
  editingId.value = null
  form.value = {
    name: '',
    type,
    api_url: '',
    api_key: '',
    model_name: '',
    input_price: 0,
    output_price: 0
  }
  formVisible.value = true
}

function openEditModal(record: ModelConfig): void {
  editingId.value = record.id
  form.value = {
    name: record.name,
    type: record.type,
    api_url: record.api_url,
    api_key: '',
    model_name: record.model_name,
    input_price: record.input_price ?? 0,
    output_price: record.output_price ?? 0
  }
  formVisible.value = true
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
    if (editingId.value) {
      // 编辑时若 api_key 为空则不传
      if (!payload.api_key) {
        delete (payload as { api_key?: string }).api_key
      }
      await updateModel(editingId.value, payload)
      message.success('保存成功')
    } else {
      await createModel(payload)
      message.success('创建成功')
    }
    formVisible.value = false
    fetchData()
    refreshStatus()
  } catch {
    // ignore
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteModel(id)
    message.success('删除成功')
    fetchData()
    refreshStatus()
  } catch {
    // ignore
  }
}

async function onActivate(record: ModelConfig & { _activating?: boolean }): Promise<void> {
  record._activating = true
  try {
    await activateModel(record.id)
    message.success('已切换启用模型')
    fetchData()
    refreshStatus()
  } catch {
    // ignore
  } finally {
    record._activating = false
  }
}

async function onTest(record: ModelConfig & { _testing?: boolean }): Promise<void> {
  record._testing = true
  try {
    testResult.value = await testModel(record.id)
    testResultVisible.value = true
  } catch {
    testResult.value = { success: false, message: '请求失败' }
    testResultVisible.value = true
  } finally {
    record._testing = false
  }
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const data = await getModelList()
    modelList.value = data || []
  } catch {
    modelList.value = []
  } finally {
    loading.value = false
  }
}

async function refreshStatus(): Promise<void> {
  try {
    const status = await getModelStatus()
    appStore.updateModelStatus(status)
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.model-config {
  max-width: 1200px;
  margin: 0 auto;
}

.model-name {
  font-weight: 600;
}

.api-url {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.65);
}

.price-hint {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}

.price-na {
  color: rgba(0, 0, 0, 0.35);
  font-size: 12px;
}

.price-cell {
  display: inline-flex;
  flex-direction: column;
  font-size: 12px;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.65);
}
</style>
