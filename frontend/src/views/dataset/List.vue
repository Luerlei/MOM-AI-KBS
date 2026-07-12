<template>
  <div class="dataset-list">
    <div class="page-toolbar">
      <div class="toolbar-left">
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索数据集名称..."
          style="width: 240px"
          allow-clear
          @search="fetchData"
        />
        <a-select
          v-model:value="filterFrequency"
          style="width: 140px"
          placeholder="数据频率"
          allow-clear
          @change="fetchData"
        >
          <a-select-option value="daily">每日</a-select-option>
          <a-select-option value="weekly">每周</a-select-option>
          <a-select-option value="monthly">每月</a-select-option>
          <a-select-option value="quarterly">每季度</a-select-option>
          <a-select-option value="yearly">每年</a-select-option>
          <a-select-option value="hourly">每小时</a-select-option>
          <a-select-option value="other">其他</a-select-option>
        </a-select>
      </div>
      <div class="toolbar-right">
        <a-dropdown>
          <a-button>
            <template #icon><DownloadOutlined /></template>
            下载模板
          </a-button>
          <template #overlay>
            <a-menu @click="onDownloadTemplate">
              <a-menu-item key="excel">Excel 模板 (.xlsx)</a-menu-item>
              <a-menu-item key="csv">CSV 模板 (.csv)</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
        <a-button type="primary" @click="showImportModal = true">
          <template #icon><UploadOutlined /></template>
          导入数据
        </a-button>
        <a-button @click="onCreate">
          <template #icon><PlusOutlined /></template>
          新增数据集
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data-source="dataList"
      :loading="loading"
      row-key="id"
      :pagination="pagination"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a-tooltip :title="record.description">
            <span>{{ record.name }}</span>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'frequency'">
          <a-tag :color="frequencyColor(record.frequency)">{{ frequencyText(record.frequency) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'source'">
          <a-tag>{{ sourceText(record.source) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="onPreview(record)">预览</a>
            <a-divider type="vertical" />
            <a @click="onAnalyze(record)">趋势分析</a>
            <a-divider type="vertical" />
            <a @click="onEvalHistory(record)">评估记录</a>
            <a-divider type="vertical" />
            <a @click="onCovariates(record)">协变量</a>
            <a-divider type="vertical" />
            <a-dropdown>
              <a>更多 <DownOutlined /></a>
              <template #overlay>
                <a-menu @click="(e) => onMenuAction(e.key, record)">
                  <a-menu-item key="edit">编辑</a-menu-item>
                  <a-menu-item key="exportExcel">导出 Excel</a-menu-item>
                  <a-menu-item key="exportCsv">导出 CSV</a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="delete" danger>删除</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 导入弹窗 -->
    <a-modal
      v-model:open="showImportModal"
      title="导入数据集"
      width="520px"
      :confirm-loading="importLoading"
      @ok="onImport"
    >
      <a-form layout="vertical">
        <a-form-item label="选择文件" required>
          <a-upload
            :before-upload="onFileSelect"
            :max-count="1"
            accept=".xlsx,.xls,.csv"
            :file-list="fileList"
            @remove="onFileRemove"
          >
            <a-button>
              <template #icon><UploadOutlined /></template>
              选择 Excel/CSV 文件
            </a-button>
          </a-upload>
          <div class="upload-tip">支持 .xlsx / .xls / .csv 格式，至少 3 个数据点</div>
        </a-form-item>
        <a-form-item label="数据集名称（可选）">
          <a-input v-model:value="importForm.name" placeholder="留空则使用文件名" />
        </a-form-item>
        <a-form-item label="数据频率">
          <a-select v-model:value="importForm.frequency">
            <a-select-option value="other">其他/未知</a-select-option>
            <a-select-option value="hourly">每小时</a-select-option>
            <a-select-option value="daily">每日</a-select-option>
            <a-select-option value="weekly">每周</a-select-option>
            <a-select-option value="monthly">每月</a-select-option>
            <a-select-option value="quarterly">每季度</a-select-option>
            <a-select-option value="yearly">每年</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="单位（可选）">
          <a-input v-model:value="importForm.unit" placeholder="如：万元、次、℃" />
        </a-form-item>
        <a-form-item label="描述（可选）">
          <a-textarea v-model:value="importForm.description" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:open="showEditModal"
      :title="editingId ? '编辑数据集' : '新增数据集'"
      width="720px"
      :confirm-loading="editLoading"
      @ok="onSave"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="editForm.name" placeholder="数据集名称" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item label="数据频率">
              <a-select v-model:value="editForm.frequency">
                <a-select-option value="other">其他/未知</a-select-option>
                <a-select-option value="hourly">每小时</a-select-option>
                <a-select-option value="daily">每日</a-select-option>
                <a-select-option value="weekly">每周</a-select-option>
                <a-select-option value="monthly">每月</a-select-option>
                <a-select-option value="quarterly">每季度</a-select-option>
                <a-select-option value="yearly">每年</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="单位">
              <a-input v-model:value="editForm.unit" placeholder="如：万元" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="描述">
              <a-input v-model:value="editForm.description" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="数据点（time / value / label）">
          <div class="data-editor">
            <a-table
              :columns="dataColumns"
              :data-source="editForm.series_data"
              row-key="_idx"
              size="small"
              :pagination="false"
              :scroll="{ y: 320 }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'time'">
                  <a-input v-model:value="record.time" size="small" placeholder="如 2024-01" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <a-input-number v-model:value="record.value" size="small" style="width:100%" />
                </template>
                <template v-else-if="column.key === 'label'">
                  <a-input v-model:value="record.label" size="small" placeholder="可选" />
                </template>
                <template v-else-if="column.key === 'op'">
                  <a-button type="link" danger size="small" @click="removeDataRow(index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top:8px" @click="addDataRow">
              <PlusOutlined /> 添加数据点
            </a-button>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 预览抽屉 -->
    <a-drawer
      v-model:open="showPreviewDrawer"
      title="数据集预览"
      width="720px"
    >
      <a-spin :spinning="previewLoading">
        <div v-if="previewData">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="名称">{{ previewData.dataset.name }}</a-descriptions-item>
            <a-descriptions-item label="频率">{{ frequencyText(previewData.dataset.frequency) }}</a-descriptions-item>
            <a-descriptions-item label="单位">{{ previewData.dataset.unit || '-' }}</a-descriptions-item>
            <a-descriptions-item label="数据点数">{{ previewData.dataset.point_count }}</a-descriptions-item>
            <a-descriptions-item label="最小值">{{ previewData.stats.min ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="最大值">{{ previewData.stats.max ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="均值">{{ previewData.stats.avg ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="末值">{{ previewData.stats.last ?? '-' }}</a-descriptions-item>
          </a-descriptions>
          <div ref="previewChartRef" style="width:100%;height:280px;margin-top:16px"></div>
          <a-table
            :columns="previewColumns"
            :data-source="previewData.points"
            row-key="time"
            size="small"
            :pagination="{ pageSize: 20 }"
            style="margin-top:16px"
          />
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import * as echarts from 'echarts'
import {
  PlusOutlined, UploadOutlined, DownloadOutlined, DownOutlined,
} from '@ant-design/icons-vue'
import {
  getDatasetList, createDataset, updateDataset, deleteDataset,
  previewDataset, importDataset, exportDatasetUrl, downloadTemplateUrl,
} from '@/api/dataset'
import type { Dataset, DatasetPreview, TimeSeriesPoint, DataFrequency } from '@/types'
import type { TableColumnsType } from 'ant-design-vue'

const router = useRouter()

// 列表数据
const dataList = ref<Dataset[]>([])
const loading = ref(false)
const searchKeyword = ref('')
const filterFrequency = ref<DataFrequency | undefined>(undefined)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
})

const columns: TableColumnsType = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '频率', dataIndex: 'frequency', key: 'frequency', width: 90 },
  { title: '点数', dataIndex: 'point_count', key: 'point_count', width: 70, align: 'center' },
  { title: '单位', dataIndex: 'unit', key: 'unit', width: 80 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 400, fixed: 'right' },
]

const dataColumns: TableColumnsType = [
  { title: '时间', key: 'time', width: 140 },
  { title: '值', key: 'value', width: 140 },
  { title: '标签', key: 'label' },
  { title: '操作', key: 'op', width: 70 },
]

const previewColumns: TableColumnsType = [
  { title: '时间', dataIndex: 'time', key: 'time' },
  { title: '值', dataIndex: 'value', key: 'value' },
  { title: '标签', dataIndex: 'label', key: 'label' },
]

// ========== 频率/来源文本映射 ==========
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
function sourceText(s: string): string {
  const m: Record<string, string> = { excel: 'Excel', csv: 'CSV', manual: '手动', seed: '示例' }
  return m[s] || s
}
function formatDate(s: string): string {
  if (!s) return ''
  try { return new Date(s).toLocaleString('zh-CN') } catch { return s }
}

// ========== 列表加载 ==========
async function fetchData() {
  loading.value = true
  try {
    const res = await getDatasetList({
      keyword: searchKeyword.value || undefined,
      frequency: filterFrequency.value,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    dataList.value = res.items
    pagination.total = res.total
  } catch {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

function onTableChange(p: any) {
  pagination.current = p.current
  pagination.pageSize = p.pageSize
  fetchData()
}

// ========== 导入 ==========
const showImportModal = ref(false)
const importLoading = ref(false)
const fileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const importForm = reactive({
  name: '', frequency: 'other', unit: '', description: '',
})

function onFileSelect(file: File) {
  selectedFile.value = file
  fileList.value = [{ uid: '-1', name: file.name, status: 'done' }]
  return false  // 阻止自动上传
}
function onFileRemove() {
  selectedFile.value = null
  fileList.value = []
}

async function onImport() {
  if (!selectedFile.value) {
    message.warning('请先选择文件')
    return
  }
  importLoading.value = true
  try {
    const result = await importDataset(selectedFile.value, {
      name: importForm.name || undefined,
      frequency: importForm.frequency,
      unit: importForm.unit,
      description: importForm.description,
    })
    message.success(`导入成功，共 ${result.dataset.point_count} 个数据点`)
    if (result.warnings.length > 0) {
      message.warning(`解析警告 ${result.warnings.length} 条，详情请查看数据`)
    }
    showImportModal.value = false
    // 重置表单
    selectedFile.value = null
    fileList.value = []
    importForm.name = ''
    importForm.unit = ''
    importForm.description = ''
    importForm.frequency = 'other'
    fetchData()
  } catch {
    // 错误已由拦截器提示
  } finally {
    importLoading.value = false
  }
}

// ========== 新增/编辑 ==========
const showEditModal = ref(false)
const editLoading = ref(false)
const editingId = ref<number | null>(null)
const editForm = reactive({
  name: '',
  frequency: 'other' as DataFrequency,
  unit: '',
  description: '',
  series_data: [] as TimeSeriesPoint[],
})

function onCreate() {
  editingId.value = null
  editForm.name = ''
  editForm.frequency = 'other'
  editForm.unit = ''
  editForm.description = ''
  editForm.series_data = [
    { time: 't1', value: 0, label: '' },
    { time: 't2', value: 0, label: '' },
    { time: 't3', value: 0, label: '' },
  ]
  showEditModal.value = true
}

async function onMenuAction(key: string, record: Dataset) {
  if (key === 'edit') {
    editingId.value = record.id
    editForm.name = record.name
    editForm.frequency = record.frequency
    editForm.unit = record.unit
    editForm.description = record.description
    // 加载完整数据（详情接口返回 series_data）
    try {
      const res = await import('@/api/dataset').then(m => m.getDatasetDetail(record.id))
      editForm.series_data = (res.series_data || []).map(p => ({ ...p }))
    } catch {
      editForm.series_data = []
    }
    if (editForm.series_data.length === 0) {
      editForm.series_data = [{ time: 't1', value: 0, label: '' }]
    }
    showEditModal.value = true
  } else if (key === 'exportExcel') {
    window.open(exportDatasetUrl(record.id, 'excel'), '_blank')
  } else if (key === 'exportCsv') {
    window.open(exportDatasetUrl(record.id, 'csv'), '_blank')
  } else if (key === 'delete') {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除数据集「${record.name}」？关联的预测任务和结果将一并删除。`,
      okType: 'danger',
      onOk: async () => {
        await deleteDataset(record.id)
        message.success('删除成功')
        fetchData()
      },
    })
  }
}

function addDataRow() {
  const idx = editForm.series_data.length + 1
  editForm.series_data.push({ time: `t${idx}`, value: 0, label: '' })
}
function removeDataRow(index: number) {
  editForm.series_data.splice(index, 1)
}

async function onSave() {
  if (!editForm.name.trim()) {
    message.warning('名称不能为空')
    return
  }
  if (editForm.series_data.length < 3) {
    message.warning('至少需要 3 个数据点')
    return
  }
  editLoading.value = true
  try {
    const payload = {
      name: editForm.name,
      frequency: editForm.frequency,
      unit: editForm.unit,
      description: editForm.description,
      series_data: editForm.series_data,
    }
    if (editingId.value) {
      await updateDataset(editingId.value, payload)
      message.success('更新成功')
    } else {
      await createDataset(payload)
      message.success('创建成功')
    }
    showEditModal.value = false
    fetchData()
  } catch {
    // 错误已由拦截器提示
  } finally {
    editLoading.value = false
  }
}

// ========== 预览 ==========
const showPreviewDrawer = ref(false)
const previewLoading = ref(false)
const previewData = ref<DatasetPreview | null>(null)
const previewChartRef = ref<HTMLElement>()
let previewChart: echarts.ECharts | null = null

async function onPreview(record: Dataset) {
  showPreviewDrawer.value = true
  previewLoading.value = true
  previewData.value = null
  // 销毁旧图表实例，确保新容器初始化
  if (previewChart) {
    previewChart.dispose()
    previewChart = null
  }
  try {
    previewData.value = await previewDataset(record.id)
    // 等待抽屉动画完成后再渲染图表（避免容器尺寸为 0）
    await nextTick()
    setTimeout(() => renderPreviewChart(), 350)
  } catch {
    // 错误已由拦截器提示
  } finally {
    previewLoading.value = false
  }
}

function renderPreviewChart() {
  if (!previewChartRef.value || !previewData.value) return
  if (!previewChart) {
    previewChart = echarts.init(previewChartRef.value)
  }
  const times = previewData.value.points.map(p => p.time)
  const values = previewData.value.points.map(p => p.value)
  // 标注点
  const markPoints: any[] = []
  previewData.value.points.forEach((p, i) => {
    if (p.label) {
      markPoints.push({ coord: [i, p.value], value: p.label, name: p.label })
    }
  })
  previewChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: times, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [{
      type: 'line',
      smooth: true,
      data: values,
      itemStyle: { color: '#1677ff' },
      areaStyle: { opacity: 0.1 },
      markPoint: markPoints.length > 0 ? { data: markPoints } : undefined,
    }],
  })
  previewChart.resize()
}

// ========== 跳转趋势分析 ==========
function onAnalyze(record: Dataset) {
  router.push(`/trends?dataset_id=${record.id}`)
}

// ========== 跳转评估记录 ==========
function onEvalHistory(record: Dataset) {
  router.push(`/trends?dataset_id=${record.id}`)
}

// ========== 跳转协变量管理 ==========
function onCovariates(record: Dataset) {
  router.push(`/datasets/${record.id}/covariates`)
}

// ========== 下载模板 ==========
function onDownloadTemplate({ key }: { key: string }) {
  window.open(downloadTemplateUrl(key as 'excel' | 'csv'), '_blank')
}

// ========== 生命周期 ==========
onMounted(() => {
  fetchData()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (previewChart) {
    previewChart.dispose()
    previewChart = null
  }
})
function onResize() {
  if (previewChart) previewChart.resize()
}
</script>

<style scoped>
.dataset-list {
  padding: 0;
}
.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-left, .toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}
.upload-tip {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}
.data-editor {
  border: 1px solid #f0f0f0;
  padding: 12px;
  border-radius: 4px;
}
</style>
