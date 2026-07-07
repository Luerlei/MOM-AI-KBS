import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import TokenStats from '@/views/TokenStats.vue'

// mock echarts
vi.mock('echarts', () => ({
  init: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn()
  })
}))

// mock API 模块
vi.mock('@/api/dashboard', () => ({
  getTokenStatsSummary: vi.fn(() =>
    Promise.resolve({
      total_tokens: 100,
      input_tokens: 50,
      output_tokens: 50,
      call_count: 5,
      trend: [],
      by_skill: [],
      by_call_type: [],
      cache_stats: { total_qa: 5, cache_hits: 2, cache_hit_rate: 40, tokens_saved: 100 }
    })
  ),
  mapTrend: vi.fn((v: any[]) => v),
  mapDimension: vi.fn((v: any[]) => v)
}))

// mock skill API（TokenStats 中 fetchSkills 调用）
vi.mock('@/api/skill', () => ({
  getSkillList: vi.fn(() => Promise.resolve([]))
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/token-stats', params: {}, query: {} })
}))

describe('TokenStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(TokenStats)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染统计卡片（含缓存命中率卡片）', async () => {
    const wrapper = mount(TokenStats)
    await flushPromises()
    const text = wrapper.text()
    // 5 个动态卡片 + 缓存命中率卡片
    expect(text).toContain('总 Token')
    expect(text).toContain('输入 Token')
    expect(text).toContain('输出 Token')
    expect(text).toContain('调用次数')
    expect(text).toContain('节省 Token')
    expect(text).toContain('缓存命中率')
  })

  it('应该存在时间范围选择器', async () => {
    const wrapper = mount(TokenStats)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('今日')
    expect(text).toContain('本周')
    expect(text).toContain('本月')
    expect(text).toContain('自定义')
  })

  it('应该渲染缓存命中详情', async () => {
    const wrapper = mount(TokenStats)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('命中 2 / 5 次')
    expect(text).toContain('100 token')
  })
})
