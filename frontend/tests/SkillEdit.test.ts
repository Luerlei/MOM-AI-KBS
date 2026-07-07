import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SkillEdit from '@/views/skill/Edit.vue'

// mock API 模块
vi.mock('@/api/skill', () => ({
  getSkillDetail: vi.fn(() =>
    Promise.resolve({
      id: 1,
      name: '已有 Skill',
      description: '描述',
      category: '通用',
      function: '通用问答',
      trigger_mode: 'keyword',
      trigger_keywords: [],
      trigger_patterns: [],
      knowledge_categories: [],
      knowledge_tags: [],
      prompt_template: '模板内容',
      enabled: true
    })
  ),
  createSkill: vi.fn(() => Promise.resolve({ id: 10, name: 'new' })),
  updateSkill: vi.fn(() => Promise.resolve({ id: 1 })),
  testSkill: vi.fn(() => Promise.resolve({ matched: true, skill_name: '通用问答' }))
}))

vi.mock('@/api/category', () => ({
  getCategoryTree: vi.fn(() => Promise.resolve([])),
  getTagList: vi.fn(() => Promise.resolve([]))
}))

vi.mock('@/api/skillOption', () => ({
  getSkillOptions: vi.fn(() => Promise.resolve([]))
}))

// mock vue-router
const pushMock = vi.fn()
const backMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock, back: backMock }),
  useRoute: () => ({ path: '/skills/edit', params: {}, query: {} })
}))

describe('SkillEdit', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mocks = {
    $router: { push: pushMock, back: backMock }
  }

  it('应该正确挂载', async () => {
    const wrapper = mount(SkillEdit, { global: { mocks } })
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染表单字段', async () => {
    const wrapper = mount(SkillEdit, { global: { mocks } })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('名称')
    expect(text).toContain('描述')
    expect(text).toContain('触发模式')
    expect(text).toContain('知识范围')
  })

  it('应该存在 Prompt 模板输入框', async () => {
    const wrapper = mount(SkillEdit, { global: { mocks } })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Prompt 模板')
    // textarea 存在
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
  })

  it('应该存在返回与保存按钮', async () => {
    const wrapper = mount(SkillEdit, { global: { mocks } })
    await flushPromises()
    // antd 按钮对 2 个中文字符自动插空格（"返回" -> "返 回"），去除空白后匹配
    const text = wrapper.text().replace(/\s+/g, '')
    expect(text).toContain('返回')
    expect(text).toContain('取消')
    expect(text).toContain('创建')
  })

  it('应该渲染 Skill 路由测试区域', async () => {
    const wrapper = mount(SkillEdit, { global: { mocks } })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Skill 路由测试')
  })
})
