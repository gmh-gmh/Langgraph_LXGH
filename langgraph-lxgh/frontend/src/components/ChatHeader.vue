<template>
  <div class="chat-header">
    <span class="chat-title">{{ title }}</span>
    <div class="header-actions">
      <button class="header-btn" @click="$emit('uploadImg')" title="上传图片">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({ title: { type: String, default: '对话' } })
defineEmits(['uploadImg'])
</script>

<style scoped>
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-xl);
  height: var(--header-height);
  background: rgba(15, 17, 23, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}
.chat-title {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}
.header-actions {
  display: flex;
  gap: var(--space-sm);
}
.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.header-btn:hover {
  color: var(--accent);
  background: var(--accent-soft);
}
</style>
