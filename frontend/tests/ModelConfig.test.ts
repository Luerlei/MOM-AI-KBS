import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ModelConfig from '@/views/ModelConfig.vue'

// mock API 模块
vi.mock('@/api/model', () => ({
  getModelList: vi.fn(() =>
    Promise.resolve([
      {
        id: 1,
        name: '生产 LLM',
        type: 'LLM',
        model_name: 'gpt-4',
        api_url: 'https://api.openai.com/v1',
        is_active: true
      },
      {
        id: 2,
        name: '向量模型',
        type: 'Embedding',
        model_name: 'text-embedding-3',
        api_url: 'https://api.openai.com/v1',
        is_active: true
      }
    ])
  ),
  createModel: vi.fn(() => Promise.resolve({ id: 3, name: 'new' })),
  updateModel: vi.fn(() => Promise.resolve({ id: 1 })),
  deleteModel: vi.fn(() => Promise.resolve()),
  activateModel: vi.fn(() => Promise.resolve({ id: 1 })),
  testModel: vi.fn(() => Promise.resolve({ success: true, message: 'ok', latency: 50 })),
  getModelStatus: vi.fn(() => Promise.resolve({ llm: null, embedding: null, forecast: null }))
}))

// mock store
vi.mock('@/stores/app', () => ({
  useAppStore: () => ({
    updateModelStatus: vi.fn(),
    toggleCollapsed: vi.fn(),
    markGuideViewed: vi.fn(),
    loadModelStatus: vi.fn(() => Promise.resolve()),
    modelStatus: { value: { llm: null, embedding: null, forecast: null } },
    collapsed: { value: false },
    needsGuide: { value: false },
    loaded: { value: true }
  })
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useRoute: () => ({ path: '/models', params: {}, query: {} })
}))

describe('ModelConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(ModelConfig)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染 LLM 与 Embedding 模型配置标题', async () => {
    const wrapper = mount(ModelConfig)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('LLM 模型配置')
    expect(text).toContain('Embedding 模型配置')
    expect(text).toContain('Forecast 时序预测模型配置')
  })

  it('应该渲染模型表格数据', async () => {
    const wrapper = mount(ModelConfig)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('生产 LLM')
    expect(text).toContain('gpt-4')
    expect(text).toContain('向量模型')
    expect(text).toContain('text-embedding-3')
  })

  it('应该存在新增按钮', async () => {
    const wrapper = mount(ModelConfig)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('新增 LLM')
    expect(text).toContain('新增 Embedding')
  })

  it('点击新增按钮应打开表单弹窗', async () => {
    const wrapper = mount(ModelConfig)
    await flushPromises()
    // 弹窗初始不可见
    expect(wrapper.text()).not.toContain('API Key')
    const buttons = wrapper.findAll('button')
    const createBtn = buttons.find((b) => b.text().includes('新增 LLM'))
    expect(createBtn).toBeTruthy()
    await createBtn!.trigger('click')
    await flushPromises()
    // 弹窗打开后应出现表单字段（弹窗 teleport 到 body，检查全局）
    expect(document.body.innerHTML).toContain('API Key')
    expect(document.body.innerHTML).toContain('模型名称')
  })
})
