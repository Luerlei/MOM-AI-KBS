<template>
  <a-layout class="main-layout">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      :trigger="null"
      class="sider"
      width="220px"
    >
      <div class="logo">
        <span v-if="!collapsed" class="logo-text">MOM AI 知识库</span>
        <span v-else class="logo-mini">AI</span>
      </div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        v-model:openKeys="openKeys"
        mode="inline"
        theme="dark"
        :items="menuItems"
        @click="onMenuClick"
      />
    </a-layout-sider>

    <a-layout :style="{ marginLeft: collapsed ? '80px' : '220px', transition: 'margin-left 0.2s' }">
      <!-- 顶部导航栏 -->
      <a-layout-header class="header">
        <div class="header-left">
          <a-button type="text" class="trigger" @click="toggleCollapsed">
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </a-button>
          <!-- 全局搜索框 -->
          <a-input-search
            v-model:value="globalSearchKeyword"
            placeholder="搜索知识库..."
            class="global-search"
            enter-button
            @search="onGlobalSearch"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input-search>
        </div>
        <div class="header-right">
          <a-tooltip title="模型状态">
            <a-badge
              :status="modelStatusDot"
              :text="modelStatusText"
            />
          </a-tooltip>
          <a-dropdown>
            <a class="user-info" @click.prevent>
              <a-avatar style="background-color: #1677ff">U</a-avatar>
              <span class="user-name">管理员</span>
            </a>
            <template #overlay>
              <a-menu>
                <a-menu-item key="settings" @click="goSettings">
                  <SettingOutlined />
                  <span style="margin-left: 8px">系统设置</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 内容区 -->
      <a-layout-content class="content">
        <!-- 面包屑导航 -->
        <div class="breadcrumb-bar">
          <a-breadcrumb>
            <a-breadcrumb-item v-for="(item, index) in breadcrumbList" :key="index">
              {{ item }}
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>
        <!-- 路由出口 -->
        <div class="page-container">
          <router-view />
        </div>
      </a-layout-content>
    </a-layout>

    <!-- 首次使用引导 -->
    <a-modal
      v-model:open="guideVisible"
      title="欢迎使用 MOM AI 知识库"
      :closable="false"
      :maskClosable="false"
      :footer="null"
      width="560px"
    >
      <a-result
        status="info"
        title="检测到尚未完成模型配置"
        sub-title="为了使用智能问答与搜索功能，请先配置 LLM 与 Embedding 模型"
      >
        <template #extra>
          <a-space>
            <a-button type="primary" @click="goToModelConfig">去配置模型</a-button>
            <a-button @click="skipGuide">稍后再说</a-button>
          </a-space>
        </template>
      </a-result>
    </a-modal>
    <AiChatButton />
  </a-layout>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SearchOutlined,
  SettingOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  CloudUploadOutlined,
  SearchOutlined as SearchMenuOutlined,
  MessageOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  BarChartOutlined,
  DashboardOutlined,
  FileSearchOutlined,
  LineChartOutlined,
  DatabaseOutlined
} from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'
import AiChatButton from '@/components/AiChatButton.vue'
import type { ItemType } from 'ant-design-vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const { collapsed, modelStatus, needsGuide, loaded } = storeToRefs(appStore)

const globalSearchKeyword = ref('')
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])
const guideVisible = ref(false)

// 菜单项配置
const menuItems = computed<ItemType[]>(() => [
  {
    key: '/dashboard',
    icon: () => h(DashboardOutlined),
    label: '首页'
  },
  {
    key: '/knowledge',
    icon: () => h(FileTextOutlined),
    label: '知识管理',
    children: [
      {
        key: '/knowledge',
        icon: () => h(AppstoreOutlined),
        label: '知识列表'
      },
      {
        key: '/knowledge/upload',
        icon: () => h(CloudUploadOutlined),
        label: '批量上传'
      }
    ]
  },
  {
    key: '/search',
    icon: () => h(SearchMenuOutlined),
    label: '搜索'
  },
  {
    key: '/qa-group',
    icon: () => h(MessageOutlined),
    label: '问答',
    children: [
      {
        key: '/qa',
        icon: () => h(MessageOutlined),
        label: '智能问答'
      },
      {
        key: '/qa/history',
        icon: () => h(HistoryOutlined),
        label: '问答历史'
      }
    ]
  },
  {
    key: '/skills',
    icon: () => h(ThunderboltOutlined),
    label: 'Skill 管理'
  },
  {
    key: '/models',
    icon: () => h(ApiOutlined),
    label: '模型配置'
  },
  {
    key: '/trends-group',
    icon: () => h(LineChartOutlined),
    label: '时序分析',
    children: [
      {
        key: '/datasets',
        icon: () => h(DatabaseOutlined),
        label: '数据集管理'
      },
      {
        key: '/trends',
        icon: () => h(LineChartOutlined),
        label: '趋势分析'
      }
    ]
  },
  {
    key: '/token-stats',
    icon: () => h(BarChartOutlined),
    label: 'Token 统计'
  },
  {
    key: '/call-logs',
    icon: () => h(FileSearchOutlined),
    label: '调用日志'
  }
])

// 面包屑
const breadcrumbList = computed<string[]>(() => {
  const bc = route.meta.breadcrumb as string[] | undefined
  return bc && bc.length ? bc : ['首页']
})

// 模型状态点
const modelStatusDot = computed<'success' | 'warning' | 'error'>(() => {
  if (!loaded.value) return 'warning'
  if (modelStatus.value.llm && modelStatus.value.embedding) return 'success'
  if (modelStatus.value.llm || modelStatus.value.embedding) return 'warning'
  return 'error'
})

const modelStatusText = computed(() => {
  if (!loaded.value) return '检测中'
  if (modelStatus.value.llm && modelStatus.value.embedding) return '模型正常'
  if (modelStatus.value.llm) return 'LLM 已配置'
  if (modelStatus.value.embedding) return '仅 Embedding'
  return '未配置'
})

// 监听路由变化，更新选中菜单
watch(
  () => route.path,
  (path) => {
    selectedKeys.value = [path]
    // 自动展开父菜单
    if (path.startsWith('/knowledge')) {
      openKeys.value = ['/knowledge']
    } else if (path.startsWith('/qa')) {
      openKeys.value = ['/qa-group']
    } else if (path.startsWith('/datasets') || path.startsWith('/trends')) {
      openKeys.value = ['/trends-group']
    } else {
      openKeys.value = []
    }
  },
  { immediate: true }
)

// 监听引导需求
watch(
  () => needsGuide.value,
  (val) => {
    if (val && loaded.value) {
      guideVisible.value = true
    }
  }
)

function toggleCollapsed(): void {
  appStore.toggleCollapsed()
}

function onMenuClick({ key }: { key: string }): void {
  router.push(key)
}

function onGlobalSearch(): void {
  if (globalSearchKeyword.value.trim()) {
    router.push({
      path: '/search',
      query: { q: globalSearchKeyword.value.trim() }
    })
  }
}

function goSettings(): void {
  router.push('/models')
}

function goToModelConfig(): void {
  guideVisible.value = false
  appStore.markGuideViewed()
  router.push('/models')
}

function skipGuide(): void {
  guideVisible.value = false
  appStore.markGuideViewed()
}

onMounted(async () => {
  await appStore.loadModelStatus()
  if (needsGuide.value) {
    guideVisible.value = true
  }
})
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
}

.sider {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  overflow: auto;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: #001529;
  border-bottom: 1px solid #1f1f1f;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.logo-mini {
  font-size: 20px;
  font-weight: 700;
}

.header {
  position: sticky;
  top: 0;
  z-index: 99;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px 0 0;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.trigger {
  font-size: 18px;
  padding: 0 12px;
}

.global-search {
  max-width: 480px;
  width: 100%;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.user-name {
  font-size: 14px;
}

.content {
  min-height: 100vh;
}

.breadcrumb-bar {
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}

.page-container {
  padding: 24px;
  min-height: calc(100vh - 56px - 56px);
}

/* 响应式：小屏幕隐藏用户名 */
@media (max-width: 768px) {
  .user-name {
    display: none;
  }
  .global-search {
    max-width: 240px;
  }
}
</style>
