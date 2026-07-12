<template>
  <div class="covariates-page">
    <!-- 顶部工具栏 -->
    <a-card size="small" style="margin-bottom: 16px">
      <a-space wrap align="center">
        <a-button @click="goBack">
          <template #icon><ArrowLeftOutlined /></template>
          返回数据集列表
        </a-button>
        <a-divider type="vertical" />
        <span class="param-label">数据集：</span>
        <a-tag color="blue">{{ datasetInfo?.name || `#${datasetId}` }}</a-tag>
        <a-tag v-if="datasetInfo?.frequency" :color="frequencyColor(datasetInfo.frequency)">
          {{ frequencyText(datasetInfo.frequency) }}
        </a-tag>
        <a-tag v-if="datasetInfo?.unit" color="default">单位：{{ datasetInfo.unit }}</a-tag>
        <a-divider type="vertical" />
        <a-button
          type="primary"
          @click="onAutoGenerate"
          :loading="autoGenerating"
        >
          <template #icon><ThunderboltOutlined /></template>
          自动生成协变量
        </a-button>
        <a-button @click="showEditModal = true; editingId = null; resetEditForm()">
          <template #icon><PlusOutlined /></template>
          新增协变量
        </a-button>
        <a-button @click="onPreview" :loading="previewLoading">
          <template #icon><EyeOutlined /></template>
          预览对齐矩阵
        </a-button>
      </a-space>
    </a-card>

    <!-- 协变量说明 -->
    <a-alert
      type="info"
      show-icon
      style="margin-bottom: 16px"
      message="协变量（外生变量）用于增强 ARIMA 等统计模型的预测能力"
      description="在趋势分析页选择 ARIMA 模型时可开启「使用协变量」开关，系统会自动构建 exog 矩阵。当前基础模型（Chronos/TimesFM）暂不支持协变量，接口已预留。"
    />

    <!-- 协变量列表 -->
    <a-table
      :columns="columns"
      :data-source="covariateList"
      :loading="loading"
      row-key="id"
      :pagination="false"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a-tooltip :title="record.description">
            <span>{{ record.name }}</span>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'code'">
          <a-tag color="cyan">{{ record.code }}</a-tag>
        </template>
        <template v-else-if="column.key === 'type'">
          <a-tag :color="typeColor(record.type)">{{ typeText(record.type) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'source_type'">
          <a-tag :color="sourceColor(record.source_type)">{{ sourceText(record.source_type) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'values'">
          <span>{{ record.values?.length || 0 }} 个点</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space size="small">
            <a-button type="link" size="small" @click="onEdit(record)">编辑</a-button>
            <a-button type="link" size="small" @click="onViewValues(record)">查看值</a-button>
            <a-button type="link" size="small" danger @click="onDelete(record)">删除</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:open="showEditModal"
      :title="editingId ? '编辑协变量' : '新增协变量'"
      width="720px"
      :confirm-loading="editLoading"
      @ok="onSave"
    >
      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item label="名称" required>
              <a-input v-model:value="editForm.name" placeholder="如：双十一促销" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="标识 code" required>
              <a-input
                v-model:value="editForm.code"
                placeholder="英文标识，如 promotion"
                :disabled="!!editingId"
              />
              <div class="form-tip">同一数据集下唯一，用作 exog 列名</div>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="类型">
              <a-select v-model:value="editForm.type">
                <a-select-option value="continuous">连续型 continuous</a-select-option>
                <a-select-option value="binary">二元型 binary</a-select-option>
                <a-select-option value="categorical">分类型 categorical</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-input v-model:value="editForm.description" placeholder="协变量说明（可选）" />
        </a-form-item>
        <a-form-item label="值（time / value）">
          <div class="data-editor">
            <div class="data-editor-toolbar">
              <a-space size="small">
                <a-input-number
                  v-model:value="futureHorizon"
                  :min="1"
                  :max="60"
                  size="small"
                  style="width: 90px"
                  placeholder="步数"
                />
                <a-button size="small" @click="onGenerateFuture" :loading="futureLoading">
                  生成未来时间点
                </a-button>
                <a-button size="small" danger @click="onClearFuture" :disabled="!hasFutureRows">
                  清除未来值
                </a-button>
              </a-space>
              <span class="form-tip">未来值用于预测时的 exog_future，未填写的未来点默认为 0</span>
            </div>
            <a-table
              :columns="valueColumns"
              :data-source="editForm.values"
              row-key="_idx"
              size="small"
              :pagination="false"
              :scroll="{ y: 280 }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'time'">
                  <a-input v-model:value="record.time" size="small" placeholder="如 2024-01" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <a-input-number v-model:value="record.value" size="small" style="width:100%" />
                </template>
                <template v-else-if="column.key === 'op'">
                  <a-button type="link" danger size="small" @click="removeValueRow(index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top:8px" @click="addValueRow">
              <PlusOutlined /> 添加数据点
            </a-button>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 查看值抽屉 -->
    <a-drawer
      v-model:open="showValuesDrawer"
      :title="`协变量值：${viewingCovariate?.name || ''}`"
      width="560"
    >
      <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
        <a-descriptions-item label="标识">{{ viewingCovariate?.code }}</a-descriptions-item>
        <a-descriptions-item label="类型">{{ typeText(viewingCovariate?.type || '') }}</a-descriptions-item>
        <a-descriptions-item label="来源">{{ sourceText(viewingCovariate?.source_type || '') }}</a-descriptions-item>
        <a-descriptions-item label="点数">{{ viewingCovariate?.values?.length || 0 }}</a-descriptions-item>
        <a-descriptions-item label="描述" :span="2">{{ viewingCovariate?.description || '—' }}</a-descriptions-item>
      </a-descriptions>
      <a-table
        :columns="valueColumns.filter(c => c.key !== 'op')"
        :data-source="viewingCovariate?.values || []"
        row-key="time"
        size="small"
        :pagination="{ pageSize: 20 }"
      />
    </a-drawer>

    <!-- 对齐矩阵预览抽屉 -->
    <a-drawer
      v-model:open="showPreviewDrawer"
      title="协变量对齐矩阵预览"
      width="840"
    >
      <a-spin :spinning="previewLoading">
        <div v-if="previewData">
          <a-alert
            type="info"
            show-icon
            style="margin-bottom: 12px"
            :message="`共 ${previewData.covariate_count} 个协变量，${previewData.point_count} 个时间点。对齐策略：精确匹配 → 日期前缀匹配 → 缺失填 0`"
          />
          <a-table
            :columns="previewColumns"
            :data-source="previewData.rows"
            row-key="time"
            size="small"
            :pagination="{ pageSize: 30 }"
            :scroll="{ x: 'max-content' }"
          />
        </div>
        <a-empty v-else description="点击「预览对齐矩阵」按钮查看" />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowLeftOutlined, PlusOutlined, ThunderboltOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import {
  listCovariates, createCovariate, updateCovariate, deleteCovariate,
  autoGenerateCovariates, previewCovariates, getFutureTimes,
} from '@/api/covariate'
import { getDatasetDetail } from '@/api/dataset'
import type {
  Covariate, CovariateForm, CovariateValuePoint,
  CovariatePreview, Dataset, DataFrequency,
} from '@/types'
import type { TableColumnsType } from 'ant-design-vue'

const route = useRoute()
const router = useRouter()

const datasetId = computed(() => Number(route.params.id))

// 数据集信息
const datasetInfo = ref<Dataset | null>(null)

// 列表
const covariateList = ref<Covariate[]>([])
const loading = ref(false)

const columns: TableColumnsType = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '标识 code', key: 'code', width: 130 },
  { title: '类型', key: 'type', width: 100 },
  { title: '来源', key: 'source_type', width: 90 },
  { title: '值点数', key: 'values', width: 90, align: 'center' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', key: 'action', width: 200, fixed: 'right' },
]

const valueColumns: TableColumnsType = [
  { title: '时间', key: 'time', width: 160 },
  { title: '值', key: 'value', width: 160 },
  { title: '操作', key: 'op', width: 70 },
]

// 预览矩阵列（动态）
const previewColumns = ref<TableColumnsType>([])

// 新增/编辑
const showEditModal = ref(false)
const editLoading = ref(false)
const editingId = ref<number | null>(null)
const editForm = reactive<CovariateForm & { values: CovariateValuePoint[] }>({
  name: '',
  code: '',
  type: 'continuous',
  values: [],
  description: '',
})

function resetEditForm() {
  editForm.name = ''
  editForm.code = ''
  editForm.type = 'continuous'
  editForm.values = [{ time: '', value: 0 }]
  editForm.description = ''
}

function addValueRow() {
  editForm.values.push({ time: '', value: 0 })
}
function removeValueRow(index: number) {
  editForm.values.splice(index, 1)
}

// 查看值抽屉
const showValuesDrawer = ref(false)
const viewingCovariate = ref<Covariate | null>(null)

// 预览抽屉
const showPreviewDrawer = ref(false)
const previewLoading = ref(false)
const previewData = ref<CovariatePreview | null>(null)

// 自动生成
const autoGenerating = ref(false)

// 未来值生成
const futureHorizon = ref(6)
const futureLoading = ref(false)
// 判断是否已有未来值行（基于数据集最后时间点之后的行）
const datasetLastTime = computed(() => {
  if (!datasetInfo.value?.series_data) return ''
  const arr = datasetInfo.value.series_data as any[]
  if (!Array.isArray(arr) || arr.length === 0) return ''
  return arr[arr.length - 1]?.time || ''
})
const hasFutureRows = computed(() => {
  const last = datasetLastTime.value
  if (!last) return false
  return editForm.values.some(p => p.time && p.time > last)
})

// ========== 文本/颜色映射 ==========
function frequencyText(f: string): string {
  const m: Record<string, string> = {
    daily: '每日', weekly: '每周', monthly: '每月',
    quarterly: '每季度', yearly: '每年', hourly: '每小时', other: '其他',
  }
  return m[f] || f
}
function frequencyColor(f: string): string {
  const m: Record<string, string> = {
    daily: 'blue', weekly: 'cyan', monthly: 'green',
    quarterly: 'orange', yearly: 'purple', hourly: 'red', other: 'default',
  }
  return m[f] || 'default'
}
function typeText(t: string): string {
  const m: Record<string, string> = { continuous: '连续型', binary: '二元型', categorical: '分类型' }
  return m[t] || t
}
function typeColor(t: string): string {
  const m: Record<string, string> = { continuous: 'blue', binary: 'orange', categorical: 'purple' }
  return m[t] || 'default'
}
function sourceText(s: string): string {
  const m: Record<string, string> = { manual: '手动', auto: '自动', template: '模板' }
  return m[s] || s
}
function sourceColor(s: string): string {
  const m: Record<string, string> = { manual: 'default', auto: 'green', template: 'cyan' }
  return m[s] || 'default'
}

// ========== 数据加载 ==========
async function fetchDatasetInfo() {
  try {
    datasetInfo.value = await getDatasetDetail(datasetId.value)
  } catch {
    datasetInfo.value = null
  }
}

async function fetchCovariates() {
  loading.value = true
  try {
    covariateList.value = await listCovariates(datasetId.value)
  } catch {
    covariateList.value = []
  } finally {
    loading.value = false
  }
}

// ========== 新增/编辑 ==========
function onEdit(record: Covariate) {
  editingId.value = record.id
  editForm.name = record.name
  editForm.code = record.code
  editForm.type = record.type
  editForm.description = record.description
  editForm.values = (record.values || []).map(p => ({ ...p }))
  if (editForm.values.length === 0) {
    editForm.values = [{ time: '', value: 0 }]
  }
  showEditModal.value = true
}

async function onSave() {
  if (!editForm.name.trim()) {
    message.warning('名称不能为空')
    return
  }
  if (!editForm.code.trim()) {
    message.warning('标识 code 不能为空')
    return
  }
  // 过滤空行
  const cleanValues = (editForm.values || []).filter(p => p.time && p.time.trim())
  editLoading.value = true
  try {
    const payload: CovariateForm = {
      name: editForm.name,
      code: editForm.code,
      type: editForm.type,
      values: cleanValues,
      description: editForm.description,
    }
    if (editingId.value) {
      await updateCovariate(editingId.value, payload)
      message.success('更新成功')
    } else {
      await createCovariate(datasetId.value, payload)
      message.success('创建成功')
    }
    showEditModal.value = false
    fetchCovariates()
  } catch {
    // 错误已由拦截器提示
  } finally {
    editLoading.value = false
  }
}

function onViewValues(record: Covariate) {
  viewingCovariate.value = record
  showValuesDrawer.value = true
}

function onDelete(record: Covariate) {
  Modal.confirm({
    title: '确认删除',
    content: `确定删除协变量「${record.name}」？`,
    okType: 'danger',
    onOk: async () => {
      await deleteCovariate(record.id)
      message.success('删除成功')
      fetchCovariates()
    },
  })
}

// ========== 自动生成 ==========
async function onAutoGenerate() {
  autoGenerating.value = true
  try {
    const res = await autoGenerateCovariates(datasetId.value, true)
    message.success(`已生成 ${res.total} 个协变量${res.skipped.length > 0 ? `（跳过 ${res.skipped.length} 个已存在）` : ''}`)
    fetchCovariates()
  } catch {
    // 错误已由拦截器提示
  } finally {
    autoGenerating.value = false
  }
}

// ========== 预览对齐矩阵 ==========
async function onPreview() {
  showPreviewDrawer.value = true
  previewLoading.value = true
  previewData.value = null
  try {
    const res = await previewCovariates(datasetId.value)
    previewData.value = res
    // 动态构建表格列
    previewColumns.value = (res.columns || []).map(c => ({
      title: c.title,
      dataIndex: c.key,
      key: c.key,
      width: c.key === 'time' ? 140 : 110,
      ellipsis: c.key !== 'time',
    }))
  } catch {
    previewData.value = null
  } finally {
    previewLoading.value = false
  }
}

// ========== 未来值生成 ==========
async function onGenerateFuture() {
  futureLoading.value = true
  try {
    const res = await getFutureTimes(datasetId.value, futureHorizon.value)
    const futureTimes = res.future_times || []
    if (futureTimes.length === 0) {
      message.warning('无法生成未来时间标签，请检查数据集时间格式')
      return
    }
    // 获取现有时间集合，避免重复
    const existing = new Set(editForm.values.map(p => p.time))
    let added = 0
    for (const t of futureTimes) {
      if (!existing.has(t)) {
        editForm.values.push({ time: t, value: 0 })
        added++
      }
    }
    message.success(`已添加 ${added} 个未来时间点（共 ${futureTimes.length} 个）`)
  } catch {
    // 错误已由拦截器提示
  } finally {
    futureLoading.value = false
  }
}

function onClearFuture() {
  const last = datasetLastTime.value
  if (!last) return
  const before = editForm.values.length
  editForm.values = editForm.values.filter(p => !p.time || p.time <= last)
  const removed = before - editForm.values.length
  if (removed > 0) {
    message.success(`已清除 ${removed} 个未来值行`)
  }
}

// ========== 返回 ==========
function goBack() {
  router.push('/datasets')
}

// ========== 生命周期 ==========
onMounted(() => {
  fetchDatasetInfo()
  fetchCovariates()
})
</script>

<style scoped>
.covariates-page {
  padding: 0;
}
.param-label {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}
.form-tip {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}
.data-editor {
  border: 1px solid #f0f0f0;
  padding: 12px;
  border-radius: 4px;
}
.data-editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
