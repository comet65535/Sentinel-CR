<script setup lang="ts">
const props = defineProps<{
  message: string
  code: string
  submitting: boolean
}>()

const emit = defineEmits<{
  (event: 'update:message', value: string): void
  (event: 'update:code', value: string): void
  (event: 'submit'): void
}>()

function onMessageInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:message', target.value)
}

function onCodeInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:code', target.value)
}

function onSubmit() {
  emit('submit')
}
</script>

<template>
  <div class="composer">
    <textarea
      class="composer-message"
      :value="props.message"
      @input="onMessageInput"
      rows="2"
      spellcheck="false"
      placeholder="告诉我你的约束，例如：不要改方法签名，只修语法"
    />
    <textarea
      class="composer-code"
      :value="props.code"
      @input="onCodeInput"
      rows="6"
      spellcheck="false"
      placeholder="贴上 Java 代码（follow-up 可留空以复用上一轮代码）"
    />
    <div class="composer-actions">
      <button class="submit-btn" :disabled="props.submitting" @click="onSubmit">
        {{ props.submitting ? '处理中…' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  border: 1px solid #d8e1ec;
  background: #fff;
  border-radius: 16px;
  padding: 0.75rem;
  display: grid;
  gap: 0.55rem;
}

.composer-message,
.composer-code {
  width: 100%;
  resize: vertical;
  border: none;
  outline: none;
  padding: 0.2rem;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #1e3342;
}

.composer-code {
  min-height: 120px;
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
}

.submit-btn {
  border: 1px solid #1a6d95;
  background: #1a6d95;
  color: #fff;
  border-radius: 999px;
  padding: 0.5rem 0.95rem;
  font-weight: 600;
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
