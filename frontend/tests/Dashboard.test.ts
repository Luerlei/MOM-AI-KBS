import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { flushPromises } from '@vue/test-utils'
import Dashboard from '@/views/Dashboard.vue'

// mock API 模块
vi.mock('@/api/dashboard', () => ({
  getDashboardStats: vi.fn(() =>
    Promise.resolve({
      knowledge_count: 5,
      skill_count: 3,
      today_qa_count: 10,
      document_count: 20
    })
  ),
  getRecentQA: vi.fn(() =>
    Promise.resolve([
      {
        id: 1,
        question: '如何使用知识库？',
        answer: '请先上传文档。',
        skill_name: '通用问答',
        created_at: '2024-01-01T00:00:00Z'
      }
    ])
  )
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/dashboard', params: {}, query: {} })
}))

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mocks = {
    $router: { push: vi.fn() }
  }

  it('应该正确挂载', async () => {
    const wrapper = mount(Dashboard, { global: { mocks } })
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染统计卡片', async () => {
    const wrapper = mount(Dashboard, { global: { mocks } })
    await flushPromises()
    // 4 个统计卡片
    const statistics = wrapper.findAll('.ant-statistic')
    expect(statistics.length).toBeGreaterThanOrEqual(1)
    // 检查统计标题文本
    expect(wrapper.text()).toContain('知识总数')
    expect(wrapper.text()).toContain('Skill 数量')
    expect(wrapper.text()).toContain('今日问答')
    expect(wrapper.text()).toContain('模型数量')
  })

  it('应该渲染统计数值', async () => {
    const wrapper = mount(Dashboard, { global: { mocks } })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('5')
    expect(text).toContain('20')
  })

  it('应该渲染最近问答列表', async () => {
    const wrapper = mount(Dashboard, { global: { mocks } })
    await flushPromises()
    expect(wrapper.text()).toContain('最近问答')
    expect(wrapper.text()).toContain('如何使用知识库？')
  })

  it('应该渲染快捷操作按钮', async () => {
    const wrapper = mount(Dashboard, { global: { mocks } })
    await flushPromises()
    expect(wrapper.text()).toContain('快捷操作')
    expect(wrapper.text()).toContain('批量上传知识')
    expect(wrapper.text()).toContain('智能问答')
  })
})
