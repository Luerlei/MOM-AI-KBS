import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Search from '@/views/Search.vue'

// mock API 模块
vi.mock('@/api/search', () => ({
  semanticSearch: vi.fn(() =>
    Promise.resolve({
      items: [
        {
          id: 1,
          title: '知识条目一',
          snippet: '这是搜索结果摘要内容',
          category_name: '通用',
          tags: [{ id: 1, name: '标签1' }],
          score: 0.95
        }
      ],
      total: 1
    })
  ),
  keywordSearch: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  getSearchHistory: vi.fn(() =>
    Promise.resolve([{ id: 1, query: '历史搜索词', created_at: '2024-01-01T00:00:00Z' }])
  )
}))

vi.mock('@/api/category', () => ({
  getCategoryTree: vi.fn(() => Promise.resolve([])),
  getTagList: vi.fn(() => Promise.resolve([]))
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/search', params: {}, query: {} })
}))

describe('Search', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(Search)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该存在搜索框', async () => {
    const wrapper = mount(Search)
    await flushPromises()
    expect(wrapper.html()).toContain('输入要搜索的内容')
  })

  it('应该渲染二次筛选区', async () => {
    const wrapper = mount(Search)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('二次筛选')
    expect(text).toContain('分类')
    expect(text).toContain('标签')
  })

  it('应该渲染搜索历史区域', async () => {
    const wrapper = mount(Search)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('搜索历史')
    expect(text).toContain('历史搜索词')
  })

  it('应该存在搜索类型选择器', async () => {
    const wrapper = mount(Search)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('语义搜索')
    expect(text).toContain('关键词')
  })

  it('应该渲染搜索结果列表', async () => {
    const wrapper = mount(Search)
    await flushPromises()
    // 初始无 query，应显示空状态
    const text = wrapper.text()
    expect(text).toContain('暂无搜索结果')
  })
})
