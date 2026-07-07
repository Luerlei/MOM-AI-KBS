import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SkillList from '@/views/skill/List.vue'

// mock API 模块
vi.mock('@/api/skill', () => ({
  getSkillList: vi.fn(() =>
    Promise.resolve([
      {
        id: 1,
        name: '通用问答',
        description: '通用知识问答',
        category: '通用',
        function: '通用问答',
        enabled: true
      }
    ])
  ),
  deleteSkill: vi.fn(() => Promise.resolve()),
  toggleSkill: vi.fn(() => Promise.resolve({ id: 1, enabled: false })),
  testSkill: vi.fn(() => Promise.resolve({ matched: true, skill_name: '通用问答' })),
  getSkillTemplates: vi.fn(() => Promise.resolve([])),
  createSkillFromTemplate: vi.fn(() => Promise.resolve({ id: 10 }))
}))

vi.mock('@/api/skillOption', () => ({
  getSkillOptions: vi.fn(() => Promise.resolve([]))
}))

// mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/skills', params: {}, query: {} })
}))

describe('SkillList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(SkillList)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染筛选区', async () => {
    const wrapper = mount(SkillList)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('筛选')
    expect(text).toContain('模块维度')
    expect(text).toContain('功能维度')
    expect(text).toContain('状态')
  })

  it('应该渲染表格数据', async () => {
    const wrapper = mount(SkillList)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Skill 列表')
    expect(text).toContain('通用问答')
  })

  it('应该存在新建按钮', async () => {
    const wrapper = mount(SkillList)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('新建 Skill')
    expect(text).toContain('从模板创建')
  })

  it('应该渲染表格操作列', async () => {
    const wrapper = mount(SkillList)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('测试')
    expect(text).toContain('编辑')
    expect(text).toContain('删除')
  })
})
