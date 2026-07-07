import { config } from '@vue/test-utils'
import Antd from 'ant-design-vue'

// 注册 ant-design-vue 全局组件，使测试中的 a-* 组件可渲染
config.global.plugins = [Antd]

// 全局 mock
config.global.mocks = {
  $t: (key: string) => key
}

// mock IntersectionObserver（ECharts / 部分 antd 组件需要）
global.IntersectionObserver = class IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as any

// mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as any

// mock matchMedia（antd 响应式组件可能用到）
if (!global.matchMedia) {
  global.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false
  })) as any
}

// mock getBoundingClientRect（jsdom 默认返回全 0，避免 antd 表格测量报错）
if (!Element.prototype.getBoundingClientRect) {
  Element.prototype.getBoundingClientRect = () => ({
    width: 0,
    height: 0,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    x: 0,
    y: 0,
    toJSON: () => ({})
  }) as any
}
