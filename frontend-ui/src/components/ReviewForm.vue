<script setup lang="ts">
const props = defineProps<{
  code: string
  submitting: boolean
}>()

const emit = defineEmits<{
  (event: 'update:code', value: string): void
  (event: 'submit'): void
}>()

function onInput(event: Event) {
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
      class="composer-input"
      :value="props.code"
      @input="onInput"
      rows="5"
      spellcheck="false"
      placeholder="贴上 Java 代码，按下提交开始分析"
    />
    <div class="composer-actions">
      <button class="submit-btn" :disabled="props.submitting" @click="onSubmit">
        {{ props.submitting ? '处理中…' : '提交分析' }}
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

.composer-input {
  width: 100%;
  resize: vertical;
  min-height: 110px;
  border: none;
  outline: none;
  padding: 0.2rem;
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #1e3342;
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
