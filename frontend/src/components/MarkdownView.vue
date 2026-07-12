<template>
  <div class="markdown-body markdown-view" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const props = defineProps<{
  content: string
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

const renderedHtml = computed(() => {
  const raw = md.render(props.content || '')
  // 统一过 DOMPurify，防止 markdown-it 输出中的潜在 XSS（如 javascript: 链接）
  return DOMPurify.sanitize(raw, {
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'],
  })
})
</script>

<style scoped>
.markdown-view {
  font-size: 14px;
  line-height: 1.8;
}
</style>
