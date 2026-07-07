import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SkillOptionManager from '@/components/SkillOptionManager.vue'

// mock API 模块
vi.mock('@/api/skillOption', () => ({
  getSkillOptions: vi.fn(() =>
    Promise.resolve([
      { id: 1, name: '通用', color: 'blue', description: '通用分类' },
      { id: 2, name: '生产', color: 'green', description: '' }
    ])
  ),
  createSkillOption: vi.fn(() => Promise.resolve({ id: 3, name: '新分类' })),
  updateSkillOption: vi.fn(() => Promise.resolve({ id: 1 })),
  deleteSkillOption: vi.fn(() => Promise.resolve())
}))

// mock vue-router（组件未使用，但保持一致）
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/test', params: {}, query: {} })
}))

describe('SkillOptionManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确挂载', async () => {
    const wrapper = mount(SkillOptionManager, {
      props: { type: 'category', modelValue: true }
    })
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('应该渲染标题', async () => {
    const wrapper = mount(SkillOptionManager, {
      props: { type: 'category', modelValue: true }
    })
    await flushPromises()
    expect(document.body.innerHTML).toContain('管理模块分类')
  })

  it('应该渲染新增表单', async () => {
    const wrapper = mount(SkillOptionManager, {
      props: { type: 'category', modelValue: true }
    })
    await flushPromises()
    const body = document.body.innerHTML
    expect(body).toContain('输入名称')
    // antd 按钮对 2 个中文字符自动插空格（"添加" -> "添 加"），去除空白后匹配
    expect(body.replace(/\s+/g, '')).toContain('添加')
  })

  it('应该渲染选项列表', async () => {
    // SkillOptionManager 的 watch 非 immediate，需通过 modelValue 由 false 变 true 触发 loadOptions
    const wrapper = mount(SkillOptionManager, {
      props: { type: 'category', modelValue: false }
    })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    const body = document.body.innerHTML
    expect(body).toContain('通用')
    expect(body).toContain('生产')
  })

  it('功能维度应渲染对应标题', async () => {
    const wrapper = mount(SkillOptionManager, {
      props: { type: 'function', modelValue: true }
    })
    await flushPromises()
    expect(document.body.innerHTML).toContain('管理功能分类')
  })
})
