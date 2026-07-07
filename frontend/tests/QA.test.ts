import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import QA from '@/views/QA.vue'

// mock API 模块
vi.mock('@/api/qa', () => ({
  askQuestionStream: vi.fn(() => Promise.resolve()),
  submitFeedback: vi.fn(() => Promise.resolve()),
  getSuggestions: vi.fn(() => Promise.resolve(['追问1', '追问2']))
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/qa', params: {}, query: {} })
}))

describe('QA', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(QA)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该存在问题输入框', async () => {
    const wrapper = mount(QA)
    await flushPromises()
    const inputs = wrapper.findAll('input')
    expect(inputs.length).toBeGreaterThanOrEqual(1)
    // 占位符文本
    expect(wrapper.html()).toContain('输入您的问题')
  })

  it('应该存在发送按钮', async () => {
    const wrapper = mount(QA)
    await flushPromises()
    const buttons = wrapper.findAll('button')
    // antd 按钮会对 2 个中文字符自动插入空格（"发送" -> "发 送"），去除空白后匹配
    const sendBtn = buttons.find((b) => b.text().replace(/\s+/g, '').includes('发送'))
    expect(sendBtn).toBeTruthy()
  })

  it('空状态应显示引导文案', async () => {
    const wrapper = mount(QA)
    await flushPromises()
    expect(wrapper.text()).toContain('开始提问')
  })

  it('发送按钮初始应禁用（无输入）', async () => {
    const wrapper = mount(QA)
    await flushPromises()
    const buttons = wrapper.findAll('button')
    const sendBtn = buttons.find((b) => b.text().replace(/\s+/g, '').includes('发送'))
    expect(sendBtn).toBeTruthy()
    // 检查原生 button 的 disabled 属性
    expect((sendBtn!.element as HTMLButtonElement).disabled).toBe(true)
  })
})
