import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import QAHistory from '@/views/QAHistory.vue'

// mock API 模块
vi.mock('@/api/qa', () => ({
  getQAHistory: vi.fn(() =>
    Promise.resolve({
      items: [
        {
          id: 1,
          question: '如何配置模型？',
          answer: '请前往模型配置页面。',
          skill_name: '通用问答',
          total_tokens: 120,
          feedback: 'useful',
          created_at: '2024-01-01T00:00:00Z'
        }
      ],
      total: 1
    })
  ),
  getQAHistoryDetail: vi.fn(() =>
    Promise.resolve({
      id: 1,
      question: '如何配置模型？',
      answer: '请前往模型配置页面。',
      skill_name: '通用问答',
      model_name: 'gpt-4',
      input_tokens: 50,
      output_tokens: 70,
      total_tokens: 120,
      created_at: '2024-01-01T00:00:00Z',
      sources: []
    })
  ),
  deleteQAHistory: vi.fn(() => Promise.resolve()),
  askQuestionStream: vi.fn(),
  submitFeedback: vi.fn(),
  getSuggestions: vi.fn()
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/qa/history', params: {}, query: {} })
}))

describe('QAHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(QAHistory)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染历史列表表格', async () => {
    const wrapper = mount(QAHistory)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('问题')
    expect(text).toContain('答案摘要')
    expect(text).toContain('操作')
  })

  it('应该渲染历史记录数据', async () => {
    const wrapper = mount(QAHistory)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('如何配置模型？')
    expect(text).toContain('通用问答')
  })

  it('应该存在搜索框', async () => {
    const wrapper = mount(QAHistory)
    await flushPromises()
    expect(wrapper.html()).toContain('搜索问题或答案')
  })

  it('应该渲染表格表头列', async () => {
    const wrapper = mount(QAHistory)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Skill')
    expect(text).toContain('Token')
    expect(text).toContain('反馈')
    expect(text).toContain('时间')
  })
})
