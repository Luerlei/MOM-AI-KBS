import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelStatus, ModelConfig } from '@/types'
import { getModelStatus } from '@/api/model'

/**
 * 全局应用状态
 */
export const useAppStore = defineStore('app', () => {
  /** 当前模型状态 */
  const modelStatus = ref<ModelStatus>({ llm: null, embedding: null, forecast: null })

  /** 是否需要首次引导 */
  const needsGuide = ref(false)

  /** 侧边栏折叠状态 */
  const collapsed = ref(false)

  /** 全局加载状态 */
  const loading = ref(false)

  /** 是否已加载过模型状态 */
  const loaded = ref(false)

  /** 是否有启用的 LLM */
  const hasActiveLLM = computed(() => !!modelStatus.value.llm)

  /** 是否有启用的 Embedding */
  const hasActiveEmbedding = computed(() => !!modelStatus.value.embedding)

  /** 是否完成首次配置 */
  const isConfigured = computed(() => hasActiveLLM.value)

  /**
   * 加载模型状态
   */
  async function loadModelStatus(): Promise<void> {
    try {
      const status = await getModelStatus()
      modelStatus.value = status
      // 仅当缺少 LLM 时才需要引导（Embedding 缺失可优雅降级）
      needsGuide.value = !status.llm
    } catch {
      // 后端未启动或接口异常，标记需要引导
      needsGuide.value = true
    } finally {
      loaded.value = true
    }
  }

  /**
   * 更新模型状态
   */
  function updateModelStatus(status: ModelStatus): void {
    modelStatus.value = status
    needsGuide.value = !status.llm
  }

  /**
   * 切换侧边栏
   */
  function toggleCollapsed(): void {
    collapsed.value = !collapsed.value
  }

  /**
   * 标记已查看引导
   */
  function markGuideViewed(): void {
    needsGuide.value = false
  }

  return {
    modelStatus,
    needsGuide,
    collapsed,
    loading,
    loaded,
    hasActiveLLM,
    hasActiveEmbedding,
    isConfigured,
    loadModelStatus,
    updateModelStatus,
    toggleCollapsed,
    markGuideViewed
  }
})

/**
 * 模型配置列表 store
 */
export const useModelStore = defineStore('model', () => {
  const list = ref<ModelConfig[]>([])
  const loaded = ref(false)

  async function setList(data: ModelConfig[]): Promise<void> {
    list.value = data
    loaded.value = true
  }

  return { list, loaded, setList }
})
