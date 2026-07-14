import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页', breadcrumb: ['首页'] }
      },
      {
        path: 'knowledge',
        name: 'KnowledgeList',
        component: () => import('@/views/knowledge/List.vue'),
        meta: { title: '知识列表', breadcrumb: ['首页', '知识管理'] }
      },
      {
        path: 'knowledge-base',
        name: 'KnowledgeBaseList',
        component: () => import('@/views/knowledge-base/List.vue'),
        meta: { title: '知识库管理', breadcrumb: ['首页', '知识库管理'] }
      },
      {
        path: 'knowledge-base/detail/:id',
        name: 'KnowledgeBaseDetail',
        component: () => import('@/views/knowledge-base/Detail.vue'),
        meta: { title: '知识库详情', breadcrumb: ['首页', '知识库管理', '详情'] }
      },
      {
        path: 'conversation',
        name: 'Conversation',
        component: () => import('@/views/conversation/Conversation.vue'),
        meta: { title: '会话问答', breadcrumb: ['首页', '会话问答'] }
      },
      {
        path: 'knowledge/upload',
        name: 'KnowledgeUpload',
        component: () => import('@/views/knowledge/Upload.vue'),
        meta: { title: '批量上传', breadcrumb: ['首页', '知识管理', '批量上传'] }
      },
      {
        path: 'knowledge/edit/:id?',
        name: 'KnowledgeEdit',
        component: () => import('@/views/knowledge/Edit.vue'),
        meta: { title: '编辑知识', breadcrumb: ['首页', '知识管理', '编辑'] }
      },
      {
        path: 'knowledge/detail/:id',
        name: 'KnowledgeDetail',
        component: () => import('@/views/knowledge/Detail.vue'),
        meta: { title: '知识详情', breadcrumb: ['首页', '知识管理', '知识详情'] }
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('@/views/Search.vue'),
        meta: { title: '搜索', breadcrumb: ['首页', '搜索'] }
      },
      {
        path: 'qa',
        name: 'QA',
        component: () => import('@/views/QA.vue'),
        meta: { title: '智能问答', breadcrumb: ['首页', '智能问答'] }
      },
      {
        path: 'qa/history',
        name: 'QAHistory',
        component: () => import('@/views/QAHistory.vue'),
        meta: { title: '问答历史', breadcrumb: ['首页', '问答历史'] }
      },
      {
        path: 'skills',
        name: 'SkillList',
        component: () => import('@/views/skill/List.vue'),
        meta: { title: 'Skill管理', breadcrumb: ['首页', 'Skill管理'] }
      },
      {
        path: 'skills/edit/:id?',
        name: 'SkillEdit',
        component: () => import('@/views/skill/Edit.vue'),
        meta: { title: '编辑Skill', breadcrumb: ['首页', 'Skill管理', '编辑'] }
      },
      {
        path: 'models',
        name: 'ModelConfig',
        component: () => import('@/views/ModelConfig.vue'),
        meta: { title: '模型配置', breadcrumb: ['首页', '模型配置'] }
      },
      {
        path: 'token-stats',
        name: 'TokenStats',
        component: () => import('@/views/TokenStats.vue'),
        meta: { title: 'Token统计', breadcrumb: ['首页', 'Token统计'] }
      },
      {
        path: 'call-logs',
        name: 'CallLogs',
        component: () => import('@/views/CallLogs.vue'),
        meta: { title: '调用日志', breadcrumb: ['首页', '调用日志'] }
      },
      {
        path: 'datasets',
        name: 'DatasetList',
        component: () => import('@/views/dataset/List.vue'),
        meta: { title: '数据集管理', breadcrumb: ['首页', '时序分析', '数据集管理'] }
      },
      {
        path: 'datasets/:id/covariates',
        name: 'DatasetCovariates',
        component: () => import('@/views/dataset/Covariates.vue'),
        meta: { title: '协变量管理', breadcrumb: ['首页', '时序分析', '数据集管理', '协变量管理'] }
      },
      {
        path: 'trends',
        name: 'Trends',
        component: () => import('@/views/Trends.vue'),
        meta: { title: '趋势分析', breadcrumb: ['首页', '时序分析', '趋势分析'] }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 认证状态缓存（避免每次路由跳转都请求后端）
let authEnabled: boolean | null = null

router.beforeEach(async (to, _from, next) => {
  const title = to.meta.title as string
  if (title) {
    document.title = `${title} - MOM AI 知识库`
  }

  // 登录页和公开页面直接放行
  if (to.meta.public || to.path === '/login') {
    next()
    return
  }

  // 首次访问时检查后端是否启用了认证
  if (authEnabled === null) {
    try {
      const { getAuthStatus } = await import('@/api/auth')
      const status = await getAuthStatus()
      authEnabled = status.auth_enabled
    } catch {
      authEnabled = false
    }
  }

  // 认证启用时检查 token
  if (authEnabled) {
    const token = localStorage.getItem('token')
    if (!token) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
  }

  next()
})

/** 重置认证状态缓存（登出或 401 时调用） */
export function resetAuthCache(): void {
  authEnabled = null
}

export default router
