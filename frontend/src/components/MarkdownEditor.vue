<template>
  <div class="markdown-editor">
    <!-- 工具栏 -->
    <div class="toolbar">
      <a-tooltip title="标题">
        <a-button type="text" size="small" @click="insertMarkdown('# ', '标题')">H1</a-button>
      </a-tooltip>
      <a-tooltip title="二级标题">
        <a-button type="text" size="small" @click="insertMarkdown('## ', '标题')">H2</a-button>
      </a-tooltip>
      <a-tooltip title="三级标题">
        <a-button type="text" size="small" @click="insertMarkdown('### ', '标题')">H3</a-button>
      </a-tooltip>
      <a-divider type="vertical" />
      <a-tooltip title="加粗">
        <a-button type="text" size="small" @click="wrapSelection('**', '**')">
          <BoldOutlined />
        </a-button>
      </a-tooltip>
      <a-tooltip title="斜体">
        <a-button type="text" size="small" @click="wrapSelection('*', '*')">
          <ItalicOutlined />
        </a-button>
      </a-tooltip>
      <a-divider type="vertical" />
      <a-tooltip title="无序列表">
        <a-button type="text" size="small" @click="insertMarkdown('- ', '列表项')">
          <UnorderedListOutlined />
        </a-button>
      </a-tooltip>
      <a-tooltip title="有序列表">
        <a-button type="text" size="small" @click="insertMarkdown('1. ', '列表项')">
          <OrderedListOutlined />
        </a-button>
      </a-tooltip>
      <a-divider type="vertical" />
      <a-tooltip title="代码块">
        <a-button type="text" size="small" @click="insertCodeBlock()">
          <CodeOutlined />
        </a-button>
      </a-tooltip>
      <a-tooltip title="链接">
        <a-button type="text" size="small" @click="insertLink()">
          <LinkOutlined />
        </a-button>
      </a-tooltip>
      <a-tooltip title="引用">
        <a-button type="text" size="small" @click="insertMarkdown('> ', '引用内容')">
          <MessageOutlined />
        </a-button>
      </a-tooltip>
    </div>
    <!-- 编辑区与预览区 -->
    <div class="editor-body">
      <div class="editor-pane">
        <textarea
          ref="textareaRef"
          :value="modelValue"
          class="editor-textarea"
          placeholder="请输入 Markdown 内容..."
          @input="onInput"
          @scroll="syncScroll"
        ></textarea>
      </div>
      <div ref="previewRef" class="preview-pane markdown-body" v-html="renderedHtml"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import {
  BoldOutlined,
  ItalicOutlined,
  UnorderedListOutlined,
  OrderedListOutlined,
  CodeOutlined,
  LinkOutlined,
  MessageOutlined
} from '@ant-design/icons-vue'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const previewRef = ref<HTMLDivElement | null>(null)

const renderedHtml = computed(() => {
  return md.render(props.modelValue || '')
})

function onInput(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
}

function syncScroll(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  if (previewRef.value) {
    const ratio = target.scrollTop / (target.scrollHeight - target.clientHeight || 1)
    previewRef.value.scrollTop =
      ratio * (previewRef.value.scrollHeight - previewRef.value.clientHeight || 1)
  }
}

/**
 * 在光标位置插入文本
 */
function insertText(before: string, after = '', placeholder = ''): void {
  const textarea = textareaRef.value
  if (!textarea) return
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selected = props.modelValue.substring(start, end) || placeholder
  const newText =
    props.modelValue.substring(0, start) + before + selected + after + props.modelValue.substring(end)
  emit('update:modelValue', newText)
  nextTick(() => {
    textarea.focus()
    textarea.setSelectionRange(start + before.length, start + before.length + selected.length)
  })
}

function insertMarkdown(prefix: string, placeholder = ''): void {
  insertText(prefix, '', placeholder)
}

function wrapSelection(before: string, after: string): void {
  insertText(before, after, '文本')
}

function insertCodeBlock(): void {
  insertText('\n```\n', '\n```\n', '代码')
}

function insertLink(): void {
  insertText('[', '](https://)', '链接文本')
}
</script>

<style scoped>
.markdown-editor {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
  flex-wrap: wrap;
}

.editor-body {
  display: flex;
  min-height: 360px;
  height: 420px;
}

.editor-pane {
  flex: 1;
  border-right: 1px solid #f0f0f0;
  overflow: hidden;
}

.editor-textarea {
  width: 100%;
  height: 100%;
  border: none;
  outline: none;
  resize: none;
  padding: 16px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  line-height: 1.6;
  background: #fff;
}

.preview-pane {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  background: #fff;
}

@media (max-width: 768px) {
  .editor-body {
    flex-direction: column;
    height: auto;
  }
  .editor-pane {
    border-right: none;
    border-bottom: 1px solid #f0f0f0;
    height: 240px;
  }
  .preview-pane {
    height: 240px;
  }
}
</style>
