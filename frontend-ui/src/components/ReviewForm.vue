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
  <section class="panel">
    <header class="section-header">
      <h2>Java Code Input</h2>
    </header>
    <textarea
      class="code-input"
      :value="props.code"
      @input="onInput"
      rows="14"
      spellcheck="false"
      placeholder="Paste Java code snippet here"
    />
    <button class="submit-btn" :disabled="props.submitting" @click="onSubmit">
      {{ props.submitting ? 'Submitting...' : 'Submit Review' }}
    </button>
  </section>
</template>

<style scoped>
.panel {
  background: #ffffff;
  border: 1px solid #d5dce4;
  border-radius: 14px;
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}

.section-header h2 {
  margin: 0;
  font-size: 1.05rem;
  color: #173647;
}

.code-input {
  width: 100%;
  resize: vertical;
  border: 1px solid #b7c8d6;
  border-radius: 10px;
  padding: 0.75rem;
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 0.9rem;
  line-height: 1.5;
  background: #f7fafc;
  color: #1f2f3a;
  box-sizing: border-box;
}

.code-input:focus {
  outline: 2px solid #3d8ac6;
  outline-offset: 1px;
}

.submit-btn {
  justify-self: start;
  border: none;
  border-radius: 999px;
  background: #136f9a;
  color: #ffffff;
  font-weight: 600;
  padding: 0.55rem 1rem;
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
