<template>
  <div class="markdown-body markdown-view" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{
  content: string
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

const renderedHtml = computed(() => md.render(props.content || ''))
</script>

<style scoped>
.markdown-view {
  font-size: 14px;
  line-height: 1.8;
}
</style>
