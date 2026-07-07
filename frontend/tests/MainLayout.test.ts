import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'

// mock pinia：storeToRefs 直接返回 store（store 内已是真实 ref）
vi.mock('pinia', () => ({
  defineStore: vi.fn(),
  storeToRefs: (store: any) => store
}))

// mock store
vi.mock('@/stores/app', () => ({
  useAppStore: () => ({
    collapsed: ref(false),
    modelStatus: ref({ llm: null, embedding: null, forecast: null }),
    needsGuide: ref(false),
    loaded: ref(true),
    toggleCollapsed: vi.fn(),
    markGuideViewed: vi.fn(),
    loadModelStatus: vi.fn(() => Promise.resolve())
  })
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/dashboard', params: {}, query: {}, meta: {} })
}))

describe('MainLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const globalConfig = {
    stubs: {
      RouterView: true,
      RouterLink: true
    }
  }

  it('应该正确挂载', async () => {
    const wrapper = mount(MainLayout, { global: globalConfig })
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染侧边栏菜单', async () => {
    const wrapper = mount(MainLayout, { global: globalConfig })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('首页')
    expect(text).toContain('知识管理')
    expect(text).toContain('Skill 管理')
    expect(text).toContain('模型配置')
    expect(text).toContain('Token 统计')
  })

  it('应该渲染顶栏模型状态', async () => {
    const wrapper = mount(MainLayout, { global: globalConfig })
    await flushPromises()
    const text = wrapper.text()
    // loaded=true 且 llm/embedding 均为 null -> "未配置"
    expect(text).toContain('未配置')
  })

  it('应该渲染 logo 文案', async () => {
    const wrapper = mount(MainLayout, { global: globalConfig })
    await flushPromises()
    expect(wrapper.text()).toContain('MOM AI 知识库')
  })

  it('应该渲染全局搜索框', async () => {
    const wrapper = mount(MainLayout, { global: globalConfig })
    await flushPromises()
    expect(wrapper.html()).toContain('搜索知识库')
  })

  it('应该渲染用户信息', async () => {
    const wrapper = mount(MainLayout, { global: globalConfig })
    await flushPromises()
    expect(wrapper.text()).toContain('管理员')
  })
})
