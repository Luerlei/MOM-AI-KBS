import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const routes: RouteRecordRaw[] = [
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

router.beforeEach((to, _from, next) => {
  const title = to.meta.title as string
  if (title) {
    document.title = `${title} - MOM AI 知识库`
  }
  next()
})

export default router
