<template>
  <div class="call-logs-page">
    <a-card title="模型调用日志" :bordered="false">
      <template #extra>
        <a-space>
          <a-select
            v-model:value="filters.call_type"
            placeholder="调用类型"
            allow-clear
            style="width: 140px"
            @change="onFilterChange"
          >
            <a-select-option value="chat">对话 (chat)</a-select-option>
            <a-select-option value="embedding">向量化 (embedding)</a-select-option>
            <a-select-option value="summary">摘要 (summary)</a-select-option>
            <a-select-option value="test">模型测试 (test)</a-select-option>
          </a-select>
          <a-input
            v-model:value="filters.model_name"
            placeholder="模型名称"
            allow-clear
            style="width: 200px"
            @press-enter="onFilterChange"
          />
          <a-select
            v-model:value="filters.time_range"
            style="width: 120px"
            @change="onFilterChange"
          >
            <a-select-option value="today">今日</a-select-option>
            <a-select-option value="week">最近 7 天</a-select-option>
            <a-select-option value="month">最近 30 天</a-select-option>
          </a-select>
          <a-button @click="onFilterChange">查询</a-button>
          <a-button @click="onReset">重置</a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="dataList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        :scroll="{ x: 1280 }"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'call_type'">
            <a-tag :color="callTypeColor(record.call_type)">{{ callTypeLabel(record.call_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'model_name'">
            <a-tag color="blue">{{ record.model_name || '-' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'source'">
            <a-tag :color="sourceColor(record.source)">{{ sourceLabel(record.source) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'question'">
            <a-tooltip :title="record.question || ''">
              <span class="question-cell">{{ record.question || '-' }}</span>
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'skill_name'">
            <a-tag v-if="record.skill_name" color="orange">{{ record.skill_name }}</a-tag>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'tokens'">
            <span class="token-cell">
              <span class="token-in">↓{{ record.input_tokens }}</span>
              <span class="token-out">↑{{ record.output_tokens }}</span>
              <span class="token-total">= {{ record.total_tokens }}</span>
            </span>
          </template>
          <template v-else-if="column.key === 'duration_ms'">
            <span :class="durationClass(record.duration_ms)">{{ record.duration_ms }} ms</span>
          </template>
          <template v-else-if="column.key === 'created_at'">
            <span class="time-cell">{{ formatTime(record.created_at) }}</span>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { getModelCallLogs } from '@/api/dashboard'
import type { ModelCallLog, PaginatedData } from '@/types'

const loading = ref(false)
const dataList = ref<ModelCallLog[]>([])
const total = ref(0)

const filters = reactive({
  call_type: undefined as string | undefined,
  model_name: '',
  time_range: 'week'
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`
})

const columns = [
  { title: 'ID', key: 'id', dataIndex: 'id', width: 70 },
  { title: '调用类型', key: 'call_type', width: 110 },
  { title: '模型', key: 'model_name', width: 180 },
  { title: '发起人', key: 'source', width: 120 },
  { title: '关联问题', key: 'question', ellipsis: true },
  { title: 'Skill', key: 'skill_name', width: 140 },
  { title: 'Token (入/出/总)', key: 'tokens', width: 200 },
  { title: '耗时', key: 'duration_ms', dataIndex: 'duration_ms', width: 110 },
  { title: '调用时间', key: 'created_at', dataIndex: 'created_at', width: 180 }
]

function callTypeLabel(t: string): string {
  const map: Record<string, string> = {
    chat: '对话',
    embedding: '向量化',
    summary: '摘要',
    test: '模型测试'
  }
  return map[t] || t
}

function callTypeColor(t: string): string {
  const map: Record<string, string> = {
    chat: 'blue',
    embedding: 'purple',
    summary: 'cyan',
    test: 'magenta'
  }
  return map[t] || 'default'
}

function sourceLabel(s: string): string {
  const map: Record<string, string> = {
    qa: '智能问答',
    qa_cache: '问答缓存',
    chat: '浮窗对话',
    search: '语义搜索',
    sync_index: '索引同步',
    skill_router: 'Skill 路由',
    test_model: '模型测试',
    internal: '内部'
  }
  return map[s] || s || '智能问答'
}

function sourceColor(s: string): string {
  const map: Record<string, string> = {
    qa: 'green',
    qa_cache: 'lime',
    chat: 'geekblue',
    search: 'orange',
    sync_index: 'gold',
    skill_router: 'volcano',
    test_model: 'magenta',
    internal: 'default'
  }
  return map[s] || 'default'
}

function durationClass(ms: number): string {
  if (!ms) return ''
  if (ms < 1000) return 'duration-fast'
  if (ms < 5000) return 'duration-normal'
  return 'duration-slow'
}

function formatTime(t: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res: PaginatedData<ModelCallLog> = await getModelCallLogs({
      time_range: filters.time_range,
      call_type: filters.call_type,
      model_name: filters.model_name.trim() || undefined,
      page: pagination.current,
      page_size: pagination.pageSize
    })
    dataList.value = res.items || []
    total.value = res.total || 0
    pagination.total = res.total || 0
  } catch (e) {
    message.error('加载调用日志失败')
    dataList.value = []
  } finally {
    loading.value = false
  }
}

function onFilterChange(): void {
  pagination.current = 1
  fetchData()
}

function onReset(): void {
  filters.call_type = undefined
  filters.model_name = ''
  filters.time_range = 'week'
  pagination.current = 1
  fetchData()
}

function onTableChange(p: { current: number; pageSize: number }): void {
  pagination.current = p.current
  pagination.pageSize = p.pageSize
  fetchData()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.call-logs-page {
  max-width: 1400px;
  margin: 0 auto;
}

.question-cell {
  display: inline-block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: rgba(0, 0, 0, 0.65);
  font-size: 13px;
}

.token-cell {
  display: inline-flex;
  gap: 8px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.token-in {
  color: #1677ff;
}

.token-out {
  color: #52c41a;
}

.token-total {
  color: rgba(0, 0, 0, 0.85);
  font-weight: 600;
}

.time-cell {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.65);
}

.duration-fast {
  color: #52c41a;
  font-weight: 500;
}

.duration-normal {
  color: #faad14;
}

.duration-slow {
  color: #ff4d4f;
  font-weight: 500;
}
</style>
