<template>
  <div class="chat-footer">
    <div v-if="image" class="img-preview">
      <img :src="image" />
      <button class="img-remove" @click="$emit('removeImg')">✕</button>
    </div>
    <div class="input-row">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="text"
          class="chat-textarea"
          :placeholder="loading ? '等待回复...' : '输入起点和终点，例如：从北京到上海...'"
          :disabled="loading"
          rows="1"
          @keydown="onKey"
          @input="autoResize"
        />
        <button
          class="send-btn"
          :class="{ visible: text.trim() || image }"
          :disabled="(!text.trim() && !image) || loading"
          @click="send"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  loading: Boolean,
  image: String,
})
const emit = defineEmits(['send', 'removeImg'])

const text = ref('')
const textareaRef = ref(null)

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  if (!text.value.trim() && !props.image) return
  emit('send', text.value.trim())
  text.value = ''
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
    }
  })
}
</script>

<style scoped>
.chat-footer {
  padding: var(--space-md) var(--space-xl) var(--space-lg);
  background: rgba(15, 17, 23, 0.85);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border-light);
}

.img-preview {
  position: relative;
  display: inline-block;
  margin-bottom: var(--space-sm);
}
.img-preview img {
  height: 72px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}
.img-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: none;
  background: var(--danger);
  color: #fff;
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
}

.input-row {
  display: flex;
  gap: var(--space-sm);
  align-items: flex-end;
}

.input-wrapper {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  padding: 6px 6px 6px 16px;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast);
}
.input-wrapper:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}

.chat-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--text-base);
  font-family: var(--font-sans);
  line-height: 1.5;
  resize: none;
  padding: 6px 0;
  max-height: 120px;
}
.chat-textarea::placeholder {
  color: var(--text-placeholder);
}
.chat-textarea:disabled {
  opacity: 0.5;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: none;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0;
  transform: scale(0.8);
  transition: all var(--duration-fast) var(--ease-spring);
  pointer-events: none;
}
.send-btn.visible {
  opacity: 1;
  transform: scale(1);
  pointer-events: auto;
}
.send-btn:hover:not(:disabled) {
  box-shadow: var(--accent-glow);
  transform: scale(1.05);
}
.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
