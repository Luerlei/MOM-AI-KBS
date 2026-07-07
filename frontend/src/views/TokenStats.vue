<template>
  <div class="token-stats">
    <!-- 时间范围选择 -->
    <a-card size="small" style="margin-bottom: 16px">
      <a-space wrap>
        <a-radio-group v-model:value="query.time_range" button-style="solid" @change="onFilterChange">
          <a-radio-button value="today">今日</a-radio-button>
          <a-radio-button value="week">本周</a-radio-button>
          <a-radio-button value="month">本月</a-radio-button>
          <a-radio-button value="custom">自定义</a-radio-button>
        </a-radio-group>
        <template v-if="query.time_range === 'custom'">
          <a-range-picker v-model:value="dateRange" @change="onDateChange" />
        </template>
        <a-divider type="vertical" />
        <a-select
          v-model:value="query.skill_id"
          placeholder="按 Skill 筛选"
          allow-clear
          style="width: 200px"
          @change="onFilterChange"
        >
          <a-select-option v-for="s in skills" :key="s.id" :value="s.id">
            {{ s.name }}
          </a-select-option>
        </a-select>
        <a-input
          v-model:value="query.model_name"
          placeholder="按模型名筛选"
          allow-clear
          style="width: 200px"
          @change="onFilterChange"
        />
      </a-space>
    </a-card>

    <!-- 统计卡片（5列） -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :xs="12" :sm="12" :lg="4" :xl="4" v-for="card in statCards" :key="card.key">
        <a-card :loading="loading" size="small" :class="{ 'clickable-card': card.key === 'calls' }" @click="card.key === 'calls' && openCallLogs()">
          <a-statistic
            :title="card.title"
            :value="card.value"
            :suffix="card.suffix"
            :value-style="{ color: card.color }"
          />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :lg="4" :xl="4">
        <a-card :loading="loading" size="small">
          <a-statistic
            title="缓存命中率"
            :value="cacheHitRate"
            suffix="%"
            :value-style="{ color: cacheHitRate >= 30 ? '#52c41a' : '#faad14' }"
          />
          <div class="cache-sub">
            命中 {{ cacheStats.cache_hits }} / {{ cacheStats.total_qa }} 次，
            节省约 {{ cacheStats.tokens_saved }} token
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 趋势图 -->
    <a-card title="Token 趋势（近7天）" style="margin-bottom: 16px">
      <a-spin :spinning="loading">
        <div ref="trendChartRef" class="chart-container"></div>
        <a-empty v-if="!loading && trendData.length === 0" description="暂无趋势数据" />
      </a-spin>
    </a-card>

    <!-- 分布图 -->
    <a-row :gutter="16">
      <a-col :xs="24" :lg="12">
        <a-card title="按 Skill 分布">
          <a-spin :spinning="loading">
            <div ref="skillChartRef" class="chart-container"></div>
            <a-empty v-if="!loading && skillStats.length === 0" description="暂无数据" />
          </a-spin>
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card title="按调用类型分布">
          <a-spin :spinning="loading">
            <div ref="typeChartRef" class="chart-container"></div>
            <a-empty v-if="!loading && typeStats.length === 0" description="暂无数据" />
          </a-spin>
        </a-card>
      </a-col>
    </a-row>

    <!-- 调用日志弹窗 -->
    <a-modal
      v-model:open="callLogVisible"
      title="调用日志"
      width="900px"
      :footer="null"
    >
      <a-table
        :columns="callLogColumns"
        :data-source="callLogs"
        :loading="callLogLoading"
        :pagination="false"
        row-key="id"
        size="small"
        :scroll="{ x: 850 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'created_at'">
            {{ record.created_at?.replace('T', ' ').slice(0, 19) }}
          </template>
          <template v-if="column.key === 'cache_hit'">
            <a-tag :color="record.cache_hit ? 'green' : 'default'">
              {{ record.cache_hit ? '命中' : '未命中' }}
            </a-tag>
          </template>
        </template>
      </a-table>
      <div v-if="callLogTotal > callLogPageSize" style="text-align: right; margin-top: 16px">
        <a-pagination
          :current="callLogPage"
          :total="callLogTotal"
          :page-size="callLogPageSize"
          size="small"
          show-quick-jumper
          @change="onCallLogPageChange"
        />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Dayjs } from 'dayjs'
import * as echarts from 'echarts'
import {
  getTokenStatsSummary,
  mapTrend,
  mapDimension,
  getCallLogs
} from '@/api/dashboard'
import { getSkillList } from '@/api/skill'
import type {
  TokenStatsSummary,
  TokenTrendPoint,
  TokenDimensionStat,
  TokenStatsQuery,
  Skill,
  CacheStats,
  CallLog
} from '@/types'

const loading = ref(false)
const summary = ref<TokenStatsSummary | null>(null)
const trendData = ref<TokenTrendPoint[]>([])
const skillStats = ref<TokenDimensionStat[]>([])
const typeStats = ref<TokenDimensionStat[]>([])
const skills = ref<Skill[]>([])

const dateRange = ref<[Dayjs, Dayjs] | null>(null)

const query = ref<TokenStatsQuery>({
  time_range: 'week',
  skill_id: undefined,
  model_name: undefined
})

// 图表
const trendChartRef = ref<HTMLDivElement | null>(null)
const skillChartRef = ref<HTMLDivElement | null>(null)
const typeChartRef = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null
let skillChart: echarts.ECharts | null = null
let typeChart: echarts.ECharts | null = null

// 统计卡片（动态计算）
const statCards = computed(() => {
  const s = summary.value
  return [
    { key: 'total', title: '总 Token', value: s?.total_tokens ?? 0, suffix: '', color: '#1677ff' },
    { key: 'input', title: '输入 Token', value: s?.input_tokens ?? 0, suffix: '', color: '#52c41a' },
    { key: 'output', title: '输出 Token', value: s?.output_tokens ?? 0, suffix: '', color: '#faad14' },
    { key: 'calls', title: '调用次数', value: s?.call_count ?? 0, suffix: '', color: '#13c2c2' },
    {
      key: 'saved',
      title: '节省 Token',
      value: cacheStats.value.tokens_saved,
      suffix: '',
      color: '#722ed1'
    }
  ]
})

const cacheStats = computed<CacheStats>(
  () =>
    summary.value?.cache_stats ?? {
      total_qa: 0,
      cache_hits: 0,
      cache_hit_rate: 0,
      tokens_saved: 0
    }
)

const cacheHitRate = computed(() => cacheStats.value.cache_hit_rate)

// 调用日志弹窗
const callLogVisible = ref(false)
const callLogLoading = ref(false)
const callLogs = ref<CallLog[]>([])
const callLogTotal = ref(0)
const callLogPage = ref(1)
const callLogPageSize = ref(20)

const callLogColumns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '问题', dataIndex: 'question', key: 'question', ellipsis: true },
  { title: 'Skill', dataIndex: 'skill_name', key: 'skill_name', width: 120 },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 150 },
  { title: '输入', dataIndex: 'input_tokens', key: 'input_tokens', width: 80, align: 'right' as const },
  { title: '输出', dataIndex: 'output_tokens', key: 'output_tokens', width: 80, align: 'right' as const },
  { title: '合计', dataIndex: 'total_tokens', key: 'total_tokens', width: 80, align: 'right' as const },
  { title: '缓存命中', dataIndex: 'cache_hit', key: 'cache_hit', width: 90, align: 'center' as const }
]

async function openCallLogs(): Promise<void> {
  callLogVisible.value = true
  callLogPage.value = 1
  await fetchCallLogs()
}

async function fetchCallLogs(): Promise<void> {
  callLogLoading.value = true
  try {
    const res = await getCallLogs({
      time_range: query.value.time_range,
      skill_id: query.value.skill_id,
      model_name: query.value.model_name,
      page: callLogPage.value,
      page_size: callLogPageSize.value
    })
    callLogs.value = res.items || []
    callLogTotal.value = res.total || 0
  } catch {
    callLogs.value = []
  } finally {
    callLogLoading.value = false
  }
}

function onCallLogPageChange(page: number): void {
  callLogPage.value = page
  fetchCallLogs()
}

function onFilterChange(): void {
  fetchAll()
}

function onDateChange(_dates: unknown, dateStrings: [string, string]): void {
  query.value.start_date = dateStrings[0] || undefined
  query.value.end_date = dateStrings[1] || undefined
  fetchAll()
}

async function fetchAll(): Promise<void> {
  loading.value = true
  try {
    const params = { ...query.value }
    if (params.time_range !== 'custom') {
      delete params.start_date
      delete params.end_date
    }
    const data = await getTokenStatsSummary(params)
    summary.value = data
    trendData.value = mapTrend(data.trend as unknown as Array<Record<string, unknown>>)
    skillStats.value = mapDimension(
      data.by_skill as unknown as Array<Record<string, unknown>>,
      'skill_name'
    )
    typeStats.value = mapDimension(
      data.by_call_type as unknown as Array<Record<string, unknown>>,
      'call_type'
    )
    await nextTick()
    renderCharts()
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchSkills(): Promise<void> {
  try {
    skills.value = await getSkillList()
  } catch {
    skills.value = []
  }
}

function renderTrendChart(): void {
  if (!trendChartRef.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  const dates = trendData.value.map((p) => p.date)
  const total = trendData.value.map((p) => p.total_tokens)
  const input = trendData.value.map((p) => p.input_tokens)
  const output = trendData.value.map((p) => p.output_tokens)
  const calls = trendData.value.map((p) => p.call_count)

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['总Token', '输入Token', '输出Token', '调用次数'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: [
      { type: 'value', name: 'Token' },
      { type: 'value', name: '次数', position: 'right' }
    ],
    series: [
      {
        name: '总Token',
        type: 'line',
        smooth: true,
        data: total,
        itemStyle: { color: '#1677ff' },
        areaStyle: { opacity: 0.2 }
      },
      { name: '输入Token', type: 'line', smooth: true, data: input, itemStyle: { color: '#52c41a' } },
      { name: '输出Token', type: 'line', smooth: true, data: output, itemStyle: { color: '#faad14' } },
      {
        name: '调用次数',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: calls,
        itemStyle: { color: '#13c2c2' }
      }
    ]
  })
  trendChart.resize()
}

function renderSkillChart(): void {
  if (!skillChartRef.value) return
  if (!skillChart) {
    skillChart = echarts.init(skillChartRef.value)
  }
  const data = skillStats.value.map((s) => ({ name: s.name, value: s.total_tokens }))
  skillChart.setOption({
    tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', type: 'scroll' },
    series: [
      {
        name: 'Token 分布',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        label: { show: false, position: 'center' },
        emphasis: { label: { show: true, fontSize: '16', fontWeight: 'bold' } },
        labelLine: { show: false },
        data
      }
    ]
  })
  skillChart.resize()
}

function renderTypeChart(): void {
  if (!typeChartRef.value) return
  if (!typeChart) {
    typeChart = echarts.init(typeChartRef.value)
  }
  const data = typeStats.value.map((s) => ({ name: s.name, value: s.total_tokens }))
  typeChart.setOption({
    tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', type: 'scroll' },
    series: [
      {
        name: '调用类型',
        type: 'pie',
        radius: '65%',
        data,
        label: { formatter: '{b}: {d}%' }
      }
    ]
  })
  typeChart.resize()
}

function renderCharts(): void {
  renderTrendChart()
  renderSkillChart()
  renderTypeChart()
}

function handleResize(): void {
  trendChart?.resize()
  skillChart?.resize()
  typeChart?.resize()
}

watch(
  () => query.value.time_range,
  () => {
    if (query.value.time_range !== 'custom') {
      fetchAll()
    }
  }
)

onMounted(() => {
  fetchSkills()
  fetchAll()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  skillChart?.dispose()
  typeChart?.dispose()
})
</script>

<style scoped>
.token-stats {
  max-width: 1400px;
  margin: 0 auto;
}

.chart-container {
  width: 100%;
  height: 320px;
}

.cache-sub {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
  line-height: 1.4;
}

.clickable-card {
  cursor: pointer;
  transition: all 0.3s;
}

.clickable-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
