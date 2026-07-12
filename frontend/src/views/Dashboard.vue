<template>
  <div class="dashboard">
    <!-- 时间范围筛选 -->
    <div class="time-filter">
      <a-radio-group v-model:value="timeRange" button-style="solid" size="small" @change="loadData">
        <a-radio-button value="today">今日</a-radio-button>
        <a-radio-button value="week">本周</a-radio-button>
        <a-radio-button value="month">本月</a-radio-button>
        <a-radio-button value="all">全部</a-radio-button>
      </a-radio-group>
    </div>

    <!-- 统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card clickable-card" :loading="loading" @click="$router.push('/knowledge')">
          <a-statistic
            title="知识总数"
            :value="stats.knowledge_count"
            :value-style="{ color: '#1677ff' }"
          >
            <template #prefix>
              <FileTextOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card clickable-card" :loading="loading" @click="$router.push('/skills')">
          <a-statistic
            title="Skill 数量"
            :value="stats.skill_count"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix>
              <ThunderboltOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card clickable-card" :loading="loading" @click="$router.push('/qa/history')">
          <a-statistic
            :title="qaCountLabel"
            :value="stats.today_qa_count"
            :value-style="{ color: '#faad14' }"
          >
            <template #prefix>
              <MessageOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card class="stat-card clickable-card" :loading="loading" @click="$router.push('/models')">
          <a-statistic
            title="模型数量"
            :value="stats.model_count"
            :value-style="{ color: '#13c2c2' }"
          >
            <template #prefix>
              <ApiOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 快捷操作 -->
    <a-card title="快捷操作" class="quick-actions" style="margin-top: 16px">
      <a-space wrap size="middle">
        <a-button type="primary" size="large" @click="$router.push('/knowledge/upload')">
          <template #icon><CloudUploadOutlined /></template>
          批量上传知识
        </a-button>
        <a-button size="large" @click="$router.push('/knowledge/edit')">
          <template #icon><PlusOutlined /></template>
          新建知识
        </a-button>
        <a-button size="large" @click="$router.push('/qa')">
          <template #icon><MessageOutlined /></template>
          智能问答
        </a-button>
        <a-button size="large" @click="$router.push('/search')">
          <template #icon><SearchOutlined /></template>
          知识搜索
        </a-button>
        <a-button size="large" @click="$router.push('/skills/edit')">
          <template #icon><ThunderboltOutlined /></template>
          创建 Skill
        </a-button>
        <a-button size="large" @click="$router.push('/models')">
          <template #icon><ApiOutlined /></template>
          模型配置
        </a-button>
      </a-space>
    </a-card>

    <!-- 最近问答 -->
    <a-card title="最近问答" class="recent-qa" style="margin-top: 16px">
      <template #extra>
        <a-button type="link" size="small" @click="$router.push('/qa/history')">
          查看全部
        </a-button>
      </template>
      <a-empty v-if="!loading && recentQA.length === 0" description="暂无问答记录" />
      <a-list v-else :data-source="recentQA" :loading="loading" item-layout="horizontal">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #avatar>
                <a-avatar style="background-color: #1677ff">Q</a-avatar>
              </template>
              <template #title>
                <span class="qa-question">{{ item.question }}</span>
              </template>
              <template #description>
                <div class="qa-answer">{{ truncateText(item.answer, 120) }}</div>
                <div class="qa-meta">
                  <span v-if="item.skill_name">
                    <a-tag color="blue">{{ item.skill_name }}</a-tag>
                  </span>
                  <span>{{ formatTime(item.created_at) }}</span>
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  FileTextOutlined,
  ThunderboltOutlined,
  MessageOutlined,
  CloudUploadOutlined,
  PlusOutlined,
  SearchOutlined,
  ApiOutlined
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import { getDashboardStats, getRecentQA } from '@/api/dashboard'
import type { DashboardStats, DashboardRecentQA } from '@/types'

const loading = ref(true)
const timeRange = ref<string>('today')
const stats = ref<DashboardStats>({
  knowledge_count: 0,
  skill_count: 0,
  today_qa_count: 0,
  document_count: 0,
  model_count: 0
})
const recentQA = ref<DashboardRecentQA[]>([])

const qaCountLabel = computed(() => {
  const map: Record<string, string> = {
    today: '今日问答',
    week: '本周问答',
    month: '本月问答',
    all: '全部问答'
  }
  return map[timeRange.value] || '问答数'
})

function truncateText(text: string, max: number): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [statsRes, qaRes] = await Promise.all([
      getDashboardStats(timeRange.value),
      getRecentQA(timeRange.value)
    ])
    stats.value = statsRes
    recentQA.value = qaRes
  } catch {
    // 错误已由全局拦截器处理
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.time-filter {
  margin-bottom: 16px;
  text-align: right;
}

.stat-card {
  border-radius: 8px;
  transition: all 0.3s;
}

.clickable-card {
  cursor: pointer;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.recent-qa .qa-question {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}

.recent-qa .qa-answer {
  color: rgba(0, 0, 0, 0.65);
  font-size: 13px;
  margin: 4px 0;
}

.recent-qa .qa-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}
</style>
