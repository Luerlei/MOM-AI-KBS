<template>
  <div class="trends-page">
    <!-- 顶部工具栏 -->
    <a-card size="small" style="margin-bottom: 16px">
      <a-space wrap align="center">
        <a-select
          v-model:value="selectedDatasetId"
          placeholder="选择数据集"
          style="width: 280px"
          show-search
          option-filter-prop="label"
          :options="datasetOptions"
          @change="onDatasetChange"
        />
        <a-select
          v-model:value="selectedModelId"
          placeholder="选择预测模型"
          style="width: 220px"
          :options="forecastModelOptions"
          @change="onModelChange"
        />
        <a-radio-group v-model:value="predictMode" button-style="solid">
          <a-radio-button value="future">预测未来</a-radio-button>
          <a-radio-button value="backtest">回测对照</a-radio-button>
        </a-radio-group>
        <template v-if="predictMode === 'backtest'">
          <span class="param-label">训练点数</span>
          <a-input-number
            v-model:value="startIndex"
            :min="3"
            :max="Math.max(3, currentPointCount - 1)"
            :precision="0"
            style="width: 110px"
          />
          <span class="param-hint">/ {{ currentPointCount }}（留 {{ backtestActualCount }} 点对照）</span>
        </template>
        <a-input-number
          v-model:value="horizon"
          :min="1"
          :max="24"
          :precision="0"
          addon-before="预测步数"
          style="width: 180px"
        />
        <a-checkbox v-model:checked="enableAnalysis">AI分析</a-checkbox>
        <a-button
          type="primary"
          :loading="predicting"
          :disabled="!selectedDatasetId || !selectedModelId"
          @click="onRunForecast"
        >
          <template #icon><ThunderboltOutlined /></template>
          开始预测
        </a-button>
        <a-button
          :disabled="!analysisText && !predicting"
          :loading="predicting"
          @click="analysisDrawerVisible = true"
        >
          <template #icon><FileTextOutlined /></template>
          AI分析报告
        </a-button>
        <a-tag v-if="switchingModel" color="processing">切换中...</a-tag>
      </a-space>
    </a-card>

    <a-empty
      v-if="!selectedDatasetId"
      description="请先选择一个数据集"
      style="padding: 60px 0"
    />

    <template v-else>
      <!-- 关键指标小卡片 第1行 -->
      <a-row :gutter="[12, 12]" style="margin-bottom: 16px">
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-blue"><DatabaseOutlined /></div>
            <a-statistic title="数据点数" :value="stats?.count ?? 0" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-cyan"><CalculatorOutlined /></div>
            <a-statistic title="均值" :value="stats?.avg ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-green"><ArrowDownOutlined /></div>
            <a-statistic title="最小值" :value="stats?.min ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-red"><ArrowUpOutlined /></div>
            <a-statistic title="最大值" :value="stats?.max ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-purple"><VerticalAlignTopOutlined /></div>
            <a-statistic title="首值" :value="stats?.first ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-orange"><VerticalAlignBottomOutlined /></div>
            <a-statistic title="末值" :value="stats?.last ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
      </a-row>

      <!-- 关键指标小卡片 第2行 -->
      <a-row :gutter="[12, 12]" style="margin-bottom: 16px">
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon" :class="trendDirColor === 'green' ? 'kpi-green' : trendDirColor === 'red' ? 'kpi-red' : 'kpi-gray'">
              <RiseOutlined v-if="trendDirColor === 'green'" />
              <FallOutlined v-else-if="trendDirColor === 'red'" />
              <MinusOutlined v-else />
            </div>
            <div class="mini-text">
              <div class="mini-label">趋势方向</div>
              <a-tag :color="trendDirColor" style="margin: 0">{{ trendDirText }}</a-tag>
            </div>
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-purple"><RocketOutlined /></div>
            <a-statistic title="趋势强度 R²" :value="stats?.trend_strength ?? 0" :precision="4" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon" :class="(stats?.growth_rate ?? 0) >= 0 ? 'kpi-green' : 'kpi-red'">
              <ArrowUpOutlined v-if="(stats?.growth_rate ?? 0) >= 0" />
              <ArrowDownOutlined v-else />
            </div>
            <a-statistic
              title="环比增长率"
              :value="stats?.growth_rate ?? 0"
              suffix="%"
              :precision="2"
              :value-style="{ color: (stats?.growth_rate ?? 0) >= 0 ? '#52c41a' : '#f5222d' }"
            />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-orange"><AlertOutlined /></div>
            <a-statistic title="波动性 CV" :value="stats?.volatility ?? 0" suffix="%" :precision="2" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-blue"><FieldTimeOutlined /></div>
            <a-statistic title="耗时" :value="forecastInfo?.duration_ms ?? 0" suffix="ms" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-cyan"><AimOutlined /></div>
            <div class="mini-text">
              <div class="mini-label">预测范围</div>
              <div class="mini-value">{{ forecastRange }}</div>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 长文本摘要卡片（占满一行） -->
      <a-card size="small" style="margin-bottom: 16px" :loading="loadingTrend">
        <template #title>
          <span><FileTextOutlined /> 数据与预测摘要</span>
        </template>
        <div class="long-summary">
          <!-- 数据集元信息 -->
          <div class="long-summary-meta">
            <span class="meta-item"><b>数据频率：</b>{{ frequencyText }}</span>
            <span class="meta-item"><b>单位：</b>{{ unitText || '—' }}</span>
          </div>
          <!-- 预测元信息 -->
          <div v-if="forecastInfo" class="long-summary-meta" style="margin-top: 8px">
            <span class="meta-item"><b>预测模型：</b>{{ forecastInfo.model_name }}</span>
            <span v-if="isBacktest" class="meta-item"><b>训练点数：</b>{{ forecastInfo.start_index }}</span>
            <span v-if="isBacktest" class="meta-item"><b>对照点数：</b>{{ forecastInfo.actuals.length }}</span>
            <span v-else class="meta-item"><b>预测步数：</b>{{ forecastInfo.forecasts.length }}</span>
            <span v-if="!isBacktest" class="meta-item"><b>预测范围：</b>{{ forecastRange }}</span>
            <span class="meta-item"><b>耗时：</b>{{ forecastInfo.duration_ms }} ms</span>
            <span class="meta-item"><b>任务 ID：</b>#{{ forecastInfo.task_id }}</span>
          </div>
          <!-- 回测误差指标 -->
          <div v-if="isBacktest && hasActuals" class="long-summary-meta" style="margin-top: 8px">
            <span class="meta-item"><b>MAE：</b>{{ fmtVal(metricsData.mae) }}{{ unitText }}</span>
            <span class="meta-item"><b>MAPE：</b>{{ Number(metricsData.mape || 0).toFixed(2) }}%</span>
            <span class="meta-item"><b>RMSE：</b>{{ fmtVal(metricsData.rmse) }}{{ unitText }}</span>
            <span class="meta-item"><b>最大误差：</b>{{ fmtVal(metricsData.max_error) }}{{ unitText }}</span>
          </div>
          <a-divider v-if="summaryText" style="margin: 12px 0" />
          <div v-if="summaryText" class="long-summary-text">{{ summaryText }}</div>
          <a-empty v-else-if="!forecastInfo" description="尚未执行预测" :image="simpleImage" />
        </div>
      </a-card>

      <!-- 趋势预测图表 -->
      <a-card title="趋势预测图表" style="margin-bottom: 16px">
        <a-spin :spinning="loadingTrend">
          <div ref="chartRef" class="chart-container"></div>
          <a-empty
            v-if="!loadingTrend && !trendData"
            description="暂无数据"
          />
        </a-spin>
        <div v-if="trendData" class="chart-legend">
          <span class="legend-item"><i class="dot history"></i>历史数据</span>
          <span class="legend-item"><i class="dot forecast"></i>预测数据</span>
          <span v-if="hasActuals" class="legend-item"><i class="dot actual"></i>实际数据</span>
          <span class="legend-item"><i class="band"></i>0.1-0.9 置信区间</span>
          <span class="legend-item"><i class="dot label"></i>标注点</span>
        </div>
      </a-card>

      <!-- 历史评估记录（图表下方） -->
      <a-card title="历史评估记录" size="small">
        <a-table
          :columns="taskColumns"
          :data-source="taskList"
          :loading="loadingTasks"
          :pagination="taskPagination"
          row-key="id"
          size="small"
          :scroll="{ x: 900 }"
          @change="onTaskPageChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
            <template v-if="column.key === 'mode'">
              <a-tag :color="record.start_index != null ? 'purple' : 'blue'" size="small">
                {{ record.start_index != null ? '回测' : '预测' }}
              </a-tag>
            </template>
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
            </template>
            <template v-if="column.key === 'duration_ms'">
              {{ record.duration_ms }} ms
            </template>
            <template v-if="column.key === 'action'">
              <a-space size="small">
                <a-button
                  type="link"
                  size="small"
                  :disabled="record.status !== 'success'"
                  @click="onViewTask(record)"
                >查看</a-button>
                <a-dropdown>
                  <a-button type="link" size="small" :disabled="record.status !== 'success'">导出</a-button>
                  <template #overlay>
                    <a-menu @click="(e) => onExportTask(record, e.key)">
                      <a-menu-item key="excel">Excel</a-menu-item>
                      <a-menu-item key="csv">CSV</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </template>

    <!-- AI 增强分析报告抽屉 -->
    <a-drawer
      v-model:open="analysisDrawerVisible"
      title="AI 增强分析报告"
      placement="right"
      width="560"
    >
      <a-spin :spinning="predicting">
        <div v-if="analysisText" class="analysis-report">
          <pre>{{ analysisText }}</pre>
        </div>
        <a-empty v-else description="执行预测后将生成 AI 分析报告" :image="simpleImage" />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { Empty, message } from 'ant-design-vue'
import { ThunderboltOutlined } from '@ant-design/icons-vue'
import {
  DatabaseOutlined, CalculatorOutlined, RiseOutlined, FallOutlined, MinusOutlined,
  RocketOutlined, ArrowUpOutlined, ArrowDownOutlined, AlertOutlined,
  FileTextOutlined, FieldTimeOutlined,
  VerticalAlignTopOutlined, VerticalAlignBottomOutlined, AimOutlined,
} from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'
import {
  getDatasetList,
} from '@/api/dataset'
import {
  runForecast,
  getTrendAnalysis,
  getForecastTasks,
  exportForecastResultUrl,
} from '@/api/forecast'
import { getModelList, activateModel } from '@/api/model'
import type {
  Dataset,
  TrendAnalysis,
  ForecastTask,
  PaginatedData,
  ModelConfig,
} from '@/types'

const route = useRoute()
const appStore = useAppStore()
const { modelStatus } = storeToRefs(appStore)

const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE

// 数据集列表
const datasets = ref<Dataset[]>([])
const selectedDatasetId = ref<number | undefined>(undefined)
const datasetOptions = computed(() =>
  datasets.value.map((d) => ({ label: `${d.name}（${d.point_count} 点）`, value: d.id }))
)

// 预测模型列表
const forecastModels = ref<ModelConfig[]>([])
const selectedModelId = ref<number | undefined>(undefined)
const switchingModel = ref(false)
const forecastModelOptions = computed(() =>
  forecastModels.value.map((m) => ({
    label: `${m.name}${m.is_active ? ' ✓' : ''}`,
    value: m.id,
  }))
)

// 预测参数
const horizon = ref(6)
const predicting = ref(false)
const predictMode = ref<'future' | 'backtest'>('future')
const startIndex = ref(12)
const enableAnalysis = ref(true)

// 趋势数据
const loadingTrend = ref(false)
const trendData = ref<TrendAnalysis | null>(null)
const analysisText = ref('')
const analysisDrawerVisible = ref(false)

// 历史任务
const loadingTasks = ref(false)
const taskList = ref<ForecastTask[]>([])
const taskTotal = ref(0)
const taskPage = ref(1)
const taskPageSize = ref(10)
const taskPagination = computed(() => ({
  current: taskPage.value,
  pageSize: taskPageSize.value,
  total: taskTotal.value,
  showSizeChanger: false,
  showTotal: (t: number) => `共 ${t} 条`,
}))

// 图表
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

// ===== 计算属性 =====
const hasForecastModel = computed(() => !!selectedModelId.value)
const forecastModelName = computed(() => {
  const m = forecastModels.value.find((m) => m.id === selectedModelId.value)
  return m?.model_name || ''
})

const stats = computed(() => trendData.value?.analysis.stats || null)
const forecastInfo = computed(() => trendData.value?.forecast || null)
const summaryText = computed(() => trendData.value?.analysis.summary || '')
const unitText = computed(() => trendData.value?.dataset.unit || '')
const frequencyText = computed(() => {
  const map: Record<string, string> = {
    daily: '每日', weekly: '每周', monthly: '每月',
    quarterly: '每季度', yearly: '每年', hourly: '每小时', other: '其他',
  }
  return map[trendData.value?.dataset.frequency || 'other'] || '其他'
})

const trendDirText = computed(() => {
  const map: Record<string, string> = { up: '上升', down: '下降', flat: '平稳' }
  return map[stats.value?.trend_direction || 'flat'] || '平稳'
})
const trendDirColor = computed(() => {
  const map: Record<string, string> = { up: 'green', down: 'red', flat: 'default' }
  return map[stats.value?.trend_direction || 'flat'] || 'default'
})

// 根据原始数据推断小数精度
const dataPrecision = computed(() => {
  const values = trendData.value?.history?.map((p) => p.value) || []
  if (values.length === 0) return 2
  let maxDecimals = 0
  for (const v of values) {
    const s = String(v)
    const dot = s.indexOf('.')
    if (dot >= 0) maxDecimals = Math.max(maxDecimals, s.length - dot - 1)
  }
  return Math.min(maxDecimals, 6)
})

const forecastRange = computed(() => {
  if (!forecastInfo.value || forecastInfo.value.forecasts.length === 0) return '—'
  const fs = forecastInfo.value.forecasts
  const p = dataPrecision.value
  return `${Math.min(...fs).toFixed(p)} ~ ${Math.max(...fs).toFixed(p)}${unitText.value}`
})

// 历史值带精度的格式化
function fmtVal(v: number | undefined | null): string {
  if (v == null) return '—'
  return Number(v).toFixed(dataPrecision.value)
}

const currentPointCount = computed(() => trendData.value?.dataset.point_count ?? 0)
const backtestActualCount = computed(() => Math.max(0, currentPointCount.value - startIndex.value))
const isBacktest = computed(() => forecastInfo.value?.is_backtest ?? false)
const hasActuals = computed(() => (forecastInfo.value?.actuals?.length ?? 0) > 0)
const metricsData = computed(() => forecastInfo.value?.metrics ?? { mae: 0, mape: 0, rmse: 0, max_error: 0 })

// ===== 任务列表列 =====
const taskColumns = [
  { title: '任务ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 180, ellipsis: true },
  { title: '模式', key: 'mode', width: 80, align: 'center' as const },
  { title: '步数', dataIndex: 'horizon', key: 'horizon', width: 70, align: 'right' as const },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90, align: 'center' as const },
  { title: '耗时', dataIndex: 'duration_ms', key: 'duration_ms', width: 100, align: 'right' as const },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 140, align: 'center' as const, fixed: 'right' as const },
]

// ===== 方法 =====
async function fetchDatasets(): Promise<void> {
  try {
    const res = await getDatasetList({ page: 1, page_size: 100 })
    datasets.value = res.items || []
    // 若 URL 带 dataset_id 参数则自动选中
    const qid = route.query.dataset_id
    if (qid && !selectedDatasetId.value) {
      const id = Number(qid)
      if (datasets.value.some((d) => d.id === id)) {
        selectedDatasetId.value = id
        await onDatasetChange(id)
        return
      }
    }
    // 默认选第一个
    if (!selectedDatasetId.value && datasets.value.length > 0) {
      selectedDatasetId.value = datasets.value[0].id
      await onDatasetChange(datasets.value[0].id)
    }
  } catch {
    datasets.value = []
  }
}

async function fetchForecastModels(): Promise<void> {
  try {
    const all = await getModelList()
    forecastModels.value = all.filter((m) => m.type === 'Forecast')
    // 默认选中当前启用的模型
    const active = forecastModels.value.find((m) => m.is_active)
    if (active) {
      selectedModelId.value = active.id
    } else if (forecastModels.value.length > 0 && !selectedModelId.value) {
      selectedModelId.value = forecastModels.value[0].id
    }
  } catch {
    forecastModels.value = []
  }
}

async function onModelChange(modelId: number): Promise<void> {
  // 选择哪个模型就自动启用哪个
  const target = forecastModels.value.find((m) => m.id === modelId)
  if (!target) return
  if (target.is_active) return  // 已启用无需切换

  switchingModel.value = true
  try {
    await activateModel(modelId)
    // 更新本地状态
    forecastModels.value.forEach((m) => (m.is_active = m.id === modelId))
    await appStore.loadModelStatus()
    message.success(`已切换到模型：${target.name}`)
  } catch (e: any) {
    message.error(e?.message || '模型切换失败')
  } finally {
    switchingModel.value = false
  }
}

async function onDatasetChange(id: number): Promise<void> {
  await Promise.all([fetchTrend(id), fetchTasks(id)])
}

async function fetchTrend(datasetId: number): Promise<void> {
  loadingTrend.value = true
  try {
    const data = await getTrendAnalysis(datasetId)
    trendData.value = data
    analysisText.value = data.forecast?.analysis || ''
    await nextTick()
    renderChart()
  } catch (e: any) {
    trendData.value = null
    analysisText.value = ''
  } finally {
    loadingTrend.value = false
  }
}

async function fetchTasks(datasetId: number): Promise<void> {
  loadingTasks.value = true
  try {
    const res: PaginatedData<ForecastTask> = await getForecastTasks(datasetId, taskPage.value, taskPageSize.value)
    taskList.value = res.items || []
    taskTotal.value = res.total || 0
  } catch {
    taskList.value = []
    taskTotal.value = 0
  } finally {
    loadingTasks.value = false
  }
}

function onTaskPageChange(pag: any): void {
  taskPage.value = pag.current
  if (selectedDatasetId.value) fetchTasks(selectedDatasetId.value)
}

async function onRunForecast(): Promise<void> {
  if (!selectedDatasetId.value) return
  predicting.value = true
  try {
    const payload: any = {
      dataset_id: selectedDatasetId.value,
      horizon: horizon.value,
      skip_analysis: !enableAnalysis.value,
    }
    if (predictMode.value === 'backtest') {
      payload.start_index = startIndex.value
    }
    const res = await runForecast(payload)
    const modeLabel = predictMode.value === 'backtest' ? '回测' : '预测'
    message.success(`${modeLabel}完成，耗时 ${res.task.duration_ms} ms`)
    // 刷新趋势与任务列表
    await Promise.all([
      fetchTrend(selectedDatasetId.value),
      fetchTasks(selectedDatasetId.value),
    ])
  } catch (e: any) {
    message.error(e?.message || '预测失败')
  } finally {
    predicting.value = false
  }
}

function onViewTask(record: ForecastTask): void {
  // 切换到该任务的预测结果：重新拉取趋势（最新结果即最近一次成功）
  // 此处简单刷新；若需查看特定历史任务，可扩展接口
  if (selectedDatasetId.value) fetchTrend(selectedDatasetId.value)
  message.info(`已展示数据集最新预测结果（任务 #${record.id}）`)
}

function onExportTask(record: ForecastTask, format: 'excel' | 'csv'): void {
  const url = exportForecastResultUrl(record.id, format)
  window.open(url, '_blank')
}

// ===== 图表渲染 =====
function renderChart(): void {
  if (!chartRef.value || !trendData.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const data = trendData.value
  const history = data.history
  const fc = data.forecast
  const backtestMode = fc?.is_backtest && (fc.actuals?.length ?? 0) > 0

  const historyTimes = history.map((p) => p.time)
  const historyValues = history.map((p) => p.value)
  const forecastValues = fc ? fc.forecasts : []
  const futureTimes = fc ? fc.future_times : []

  let allTimes: string[]
  let historySeries: (number | null)[]
  let forecastSeries: (number | null)[]
  let actualSeries: (number | null)[]
  let lowerSeries: (number | null)[]
  let bandSeries: (number | null)[]
  let forecastStartIdx: number  // forecast 起点在 allTimes 中的索引

  if (backtestMode) {
    // 回测模式：future_times 是 historyTimes 的子集
    // allTimes = historyTimes（不追加 future_times，避免重复）
    allTimes = [...historyTimes]
    forecastStartIdx = fc!.start_index ?? 0
    const trainEnd = forecastStartIdx  // 训练数据最后一个点的索引

    // 历史系列：训练区间[0, trainEnd) 显示，对照区间[trainEnd, N) 设为 null（用 actual 线展示）
    historySeries = historyValues.map((v, i) => i < trainEnd ? v : null)
    // 训练段末尾连接预测段
    if (trainEnd > 0) {
      historySeries[trainEnd - 1] = historyValues[trainEnd - 1]
    }

    // 预测系列：训练区间 null，连接点 + 预测值
    forecastSeries = historyTimes.map(() => null)
    if (trainEnd > 0) {
      forecastSeries[trainEnd - 1] = historyValues[trainEnd - 1]
    }
    forecastValues.forEach((v, i) => {
      if (trainEnd + i < forecastSeries.length) {
        forecastSeries[trainEnd + i] = v
      }
    })

    // 实际值系列：从训练末点连接，显示对照区间全部真实值（不截断于预测步数）
    actualSeries = historyTimes.map(() => null)
    if (trainEnd > 0) {
      actualSeries[trainEnd - 1] = historyValues[trainEnd - 1]
    }
    for (let i = trainEnd; i < historyValues.length; i++) {
      actualSeries[i] = historyValues[i]
    }

    // 置信区间（基于预测段位置）
    lowerSeries = historyTimes.map(() => null)
    bandSeries = historyTimes.map(() => null)
  } else {
    // 未来预测模式：future_times 是新时间标签
    allTimes = [...historyTimes, ...futureTimes]
    forecastStartIdx = historyValues.length

    historySeries = [...historyValues, ...futureTimes.map(() => null)]
    forecastSeries = historyTimes.map(() => null)
    if (forecastValues.length > 0 && historyValues.length > 0) {
      forecastSeries[historyValues.length - 1] = historyValues[historyValues.length - 1]
    }
    forecastValues.forEach((v, i) => {
      forecastSeries[historyValues.length + i] = v
    })

    actualSeries = []
    lowerSeries = [...historyTimes.map(() => null), ...futureTimes.map(() => null)]
    bandSeries = [...historyTimes.map(() => null), ...futureTimes.map(() => null)]
  }

  // 置信区间带（0.1 - 0.9）
  const quantiles = fc?.quantiles || {}
  const p10: number[] = quantiles['0.1'] || []
  const p90: number[] = quantiles['0.9'] || []
  const hasBand = p10.length > 0 && p90.length > 0

  if (hasBand) {
    p10.forEach((v, i) => {
      lowerSeries[forecastStartIdx + i] = v
    })
    p90.forEach((v, i) => {
      const lo = p10[i] ?? v
      bandSeries[forecastStartIdx + i] = v - lo
    })
  }

  // 标注点（label 非空的历史点）
  const markPoints: any[] = []
  history.forEach((p, i) => {
    if (p.label && p.label.trim()) {
      markPoints.push({
        name: p.label,
        coord: [p.time, p.value],
        value: p.label,
        symbolSize: 28,
        itemStyle: { color: '#faad14' },
        label: { show: true, formatter: p.label, fontSize: 10, color: '#fff' },
      })
    }
  })

  // 预测起点虚线
  const markLines: any[] = []
  if (fc && allTimes.length > 0 && forecastStartIdx < allTimes.length) {
    markLines.push({
      xAxis: allTimes[forecastStartIdx],
      lineStyle: { type: 'dashed', color: '#fa8c16', width: 1.5 },
      label: { formatter: backtestMode ? '回测起点' : '预测起点', position: 'insideEndTop', fontSize: 10 },
    })
  }

  const series: any[] = [
    {
      name: '历史数据',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      data: historySeries,
      itemStyle: { color: '#1677ff' },
      lineStyle: { color: '#1677ff', width: 2 },
      markPoint: markPoints.length > 0 ? { data: markPoints } : undefined,
      markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines } : undefined,
      z: 3,
    },
  ]

  if (fc) {
    series.push({
      name: '预测数据',
      type: 'line',
      smooth: true,
      symbol: 'diamond',
      symbolSize: 7,
      data: forecastSeries,
      itemStyle: { color: '#fa8c16' },
      lineStyle: { color: '#fa8c16', width: 2, type: 'dashed' },
      z: 3,
    })
  }

  if (backtestMode) {
    series.push({
      name: '实际数据',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: actualSeries,
      itemStyle: { color: '#52c41a' },
      lineStyle: { color: '#52c41a', width: 2 },
      z: 3,
    })
  }

  if (hasBand) {
    series.push({
      name: '置信下界',
      type: 'line',
      symbol: 'none',
      stack: 'ci-band',
      data: lowerSeries,
      lineStyle: { opacity: 0 },
      z: 1,
      tooltip: { show: false },
    })
    series.push({
      name: '置信区间',
      type: 'line',
      symbol: 'none',
      stack: 'ci-band',
      data: bandSeries,
      lineStyle: { opacity: 0 },
      areaStyle: { color: 'rgba(250, 140, 22, 0.18)' },
      z: 1,
      tooltip: { show: false },
    })
  }

  const legendNames = ['历史数据', '预测数据']
  if (backtestMode) legendNames.push('实际数据')
  if (hasBand) legendNames.push('置信区间')

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: {
      data: legendNames,
      top: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 40, containLabel: true },
    xAxis: { type: 'category', data: allTimes, boundaryGap: false, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: unitText.value || '值', scale: true },
    series,
  }, true)
  chart.resize()
}

function handleResize(): void {
  chart?.resize()
}

// ===== 辅助 =====
function formatTime(s: string): string {
  return s ? s.replace('T', ' ').slice(0, 19) : ''
}
function statusText(s: string): string {
  const map: Record<string, string> = { pending: '等待', running: '运行中', success: '成功', failed: '失败' }
  return map[s] || s
}
function statusColor(s: string): string {
  const map: Record<string, string> = { pending: 'default', running: 'processing', success: 'green', failed: 'red' }
  return map[s] || 'default'
}

// ===== 生命周期 =====
watch(
  () => modelStatus.value.forecast,
  () => { /* 触发响应式更新 */ }
)

onMounted(async () => {
  await Promise.all([
    appStore.loadModelStatus(),
    fetchForecastModels(),
    fetchDatasets(),
  ])
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.trends-page {
  max-width: 1400px;
  margin: 0 auto;
}

.chart-container {
  width: 100%;
  height: 420px;
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 8px;
  padding: 8px 0 0;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.65);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.dot.history {
  background: #1677ff;
}

.dot.forecast {
  background: #fa8c16;
}

.dot.actual {
  background: #52c41a;
}

.dot.label {
  background: #faad14;
}

.band {
  display: inline-block;
  width: 18px;
  height: 10px;
  background: rgba(250, 140, 22, 0.35);
  border: 1px solid #fa8c16;
}

.stat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.stat-row span {
  color: rgba(0, 0, 0, 0.55);
}

.stat-row b {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
}

.text-up {
  color: #52c41a;
}

.text-down {
  color: #f5222d;
}

.text-warn {
  color: #faad14;
}

.param-label {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.param-hint {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

/* 小卡片样式（统一尺寸） */
.mini-card {
  position: relative;
  overflow: hidden;
  height: 100%;
}

.mini-card :deep(.ant-card-body) {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 96px;
  box-sizing: border-box;
}

.mini-card :deep(.ant-statistic) {
  flex: 1;
  min-width: 0;
}

.mini-card :deep(.ant-statistic-title) {
  font-size: 12px;
  margin-bottom: 4px;
  color: rgba(0, 0, 0, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-card :deep(.ant-statistic-content) {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  flex-shrink: 0;
}

.mini-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-label {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-value {
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  line-height: 1.4;
  word-break: break-all;
}

.kpi-blue { background: #1677ff; }
.kpi-cyan { background: #13c2c2; }
.kpi-green { background: #52c41a; }
.kpi-red { background: #f5222d; }
.kpi-orange { background: #fa8c16; }
.kpi-purple { background: #722ed1; }
.kpi-gray { background: #8c8c8c; }
.kpi-warn { background: #faad14; }

.kpi-highlight {
  border-left: 3px solid #faad14;
}

/* 长文本摘要卡片 */
.long-summary {
  width: 100%;
}

.long-summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.8;
}

.long-summary-meta .meta-item {
  white-space: nowrap;
}

.long-summary-meta .meta-item b {
  color: rgba(0, 0, 0, 0.45);
  font-weight: 500;
  margin-right: 4px;
}

.long-summary-text {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.75);
  line-height: 1.8;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.analysis-report {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 16px 20px;
}

.analysis-report pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.8;
  color: rgba(0, 0, 0, 0.85);
}
</style>
