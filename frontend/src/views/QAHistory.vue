<template>
  <div class="qa-history">
    <a-card>
      <!-- 搜索 -->
      <div class="toolbar">
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索问题或答案"
          style="width: 320px"
          allow-clear
          @search="fetchData"
        />
      </div>

      <!-- 列表 -->
      <a-table
        :columns="columns"
        :data-source="tableData"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'question'">
            <a class="question-link" @click="goDetail(record.id)">{{ record.question }}</a>
          </template>
          <template v-else-if="column.key === 'answer'">
            <span class="answer-summary">{{ truncateText(record.answer, 80) }}</span>
          </template>
          <template v-else-if="column.key === 'skill_name'">
            <a-tag v-if="record.skill_name" color="blue">{{ record.skill_name }}</a-tag>
            <span v-else class="text-muted">-</span>
          </template>
          <template v-else-if="column.key === 'total_tokens'">
            <span v-if="record.total_tokens">{{ record.total_tokens }}</span>
            <span v-else class="text-muted">-</span>
          </template>
          <template v-else-if="column.key === 'feedback'">
            <a-tag v-if="record.feedback === 'useful'" color="success">有用</a-tag>
            <a-tag v-else-if="record.feedback === 'useless'" color="error">无用</a-tag>
            <span v-else class="text-muted">未反馈</span>
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="goDetail(record.id)">查看</a-button>
              <a-popconfirm title="确定删除该问答记录?" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:open="detailVisible"
      title="问答详情"
      width="760px"
      :footer="null"
    >
      <a-spin :spinning="detailLoading">
        <div v-if="detail" class="detail-modal">
          <div class="detail-question">
            <div class="label">问题：</div>
            <div class="content">{{ detail.question }}</div>
          </div>
          <a-divider />
          <div class="detail-answer">
            <div class="label">回答：</div>
            <div class="content markdown-body" v-html="renderMd(detail.answer)"></div>
          </div>
          <a-divider />
          <div class="detail-info">
            <a-descriptions :column="2" size="small">
              <a-descriptions-item label="Skill">
                {{ detail.skill_name || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="模型">
                {{ detail.model_name || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="输入Token">
                {{ detail.input_tokens ?? '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="输出Token">
                {{ detail.output_tokens ?? '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="总Token">
                {{ detail.total_tokens ?? '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="时间">
                {{ formatTime(detail.created_at) }}
              </a-descriptions-item>
            </a-descriptions>
          </div>
          <!-- 来源 -->
          <div v-if="detail.sources && detail.sources.length > 0" class="detail-sources">
            <div class="label">参考来源：</div>
            <div class="sources-list">
              <a-tag
                v-for="(src, idx) in detail.sources"
                :key="idx"
                color="blue"
                style="cursor: pointer"
                @click="goKnowledge(src.knowledge_id)"
              >
                {{ idx + 1 }}. {{ src.title }}
              </a-tag>
            </div>
          </div>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import MarkdownIt from 'markdown-it'
import { getQAHistory, getQAHistoryDetail, deleteQAHistory } from '@/api/qa'
import type { QAHistory, PaginatedData } from '@/types'

const router = useRouter()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const detail = ref<QAHistory | null>(null)
const tableData = ref<QAHistory[]>([])

const query = ref({
  page: 1,
  page_size: 10,
  keyword: ''
})

const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
})

const columns = [
  { title: '问题', key: 'question', dataIndex: 'question', ellipsis: true },
  { title: '答案摘要', key: 'answer', dataIndex: 'answer', ellipsis: true, width: 320 },
  { title: 'Skill', key: 'skill_name', dataIndex: 'skill_name', width: 120 },
  { title: 'Token', key: 'total_tokens', dataIndex: 'total_tokens', width: 90 },
  { title: '反馈', key: 'feedback', dataIndex: 'feedback', width: 90 },
  { title: '时间', key: 'created_at', dataIndex: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' as const }
]

function truncateText(text: string, max: number): string {
  if (!text) return ''
  const plain = text.replace(/[#*`_\-\[\]()>~]/g, '').replace(/\n+/g, ' ').trim()
  return plain.length > max ? plain.slice(0, max) + '...' : plain
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

function renderMd(text: string): string {
  return md.render(text || '')
}

function onTableChange(pag: { current?: number; pageSize?: number }): void {
  query.value.page = pag.current || 1
  query.value.page_size = pag.pageSize || 10
  pagination.value.current = query.value.page
  pagination.value.pageSize = query.value.page_size
  fetchData()
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res: PaginatedData<QAHistory> = await getQAHistory({
      page: query.value.page,
      page_size: query.value.page_size,
      keyword: query.value.keyword || undefined
    })
    tableData.value = res.items || []
    pagination.value.total = res.total || 0
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function goDetail(id: number): Promise<void> {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getQAHistoryDetail(id)
  } catch {
    // ignore
  } finally {
    detailLoading.value = false
  }
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteQAHistory(id)
    message.success('删除成功')
    fetchData()
  } catch {
    // ignore
  }
}

function goKnowledge(id: number): void {
  if (id) {
    router.push(`/knowledge/detail/${id}`)
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.qa-history {
  max-width: 1400px;
  margin: 0 auto;
}

.toolbar {
  padding: 16px;
  display: flex;
  justify-content: space-between;
}

.question-link {
  font-weight: 500;
}

.answer-summary {
  color: rgba(0, 0, 0, 0.65);
  font-size: 13px;
}

.text-muted {
  color: rgba(0, 0, 0, 0.45);
}

.detail-modal .label {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  margin-bottom: 4px;
}

.detail-question .content {
  font-size: 15px;
  font-weight: 500;
}

.detail-answer .content {
  line-height: 1.8;
}

.detail-sources {
  margin-top: 16px;
}

.sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
</style>
