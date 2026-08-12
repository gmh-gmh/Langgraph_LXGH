<template>
  <div class="sidebar">
    <div class="sidebar-top">
      <div class="logo-row">
        <div class="logo-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </div>
        <span class="logo-text">路线规划</span>
      </div>
      <button class="new-btn" @click="$emit('newChat')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        新建对话
      </button>
    </div>

    <div class="conv-list">
      <div
        v-for="conv in conversations"
        :key="conv.id"
        class="conv-item"
        :class="{ active: conv.id === currentConvId }"
        @click="$emit('switchConv', conv.id)">
        <div class="conv-title">{{ conv.title }}</div>
        <button class="conv-del" @click.stop="$emit('deleteConv', conv.id)">✕</button>
      </div>
      <div v-if="conversations.length === 0" class="conv-empty">暂无对话</div>
    </div>

    <div class="sidebar-bottom">
      <div class="mode-tags">
        <span class="mode-tag" :class="{ active: hasMode('driving') }"
          @click="toggleMode('driving')" title="驾车">🚗</span>
        <span class="mode-tag" :class="{ active: hasMode('transit') }"
          @click="toggleMode('transit')" title="公共交通">🚇</span>
        <span class="mode-tag" :class="{ active: hasMode('walking') }"
          @click="toggleMode('walking')" title="步行">🚶</span>
      </div>
      <div class="sidebar-foot">
        <span class="dot" :class="{ on: connected }"></span>
        <span class="status">{{ connected ? '已连接' : '断开连接' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  connected: Boolean,
  conversations: { type: Array, default: () => [] },
  currentConvId: String,
  profile: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['newChat', 'switchConv', 'deleteConv', 'updateProfile'])

function hasMode(mode) {
  return (props.profile?.preferred_modes || []).includes(mode)
}
function toggleMode(mode) {
  const modes = [...(props.profile?.preferred_modes || [])]
  const idx = modes.indexOf(mode)
  if (idx > -1) modes.splice(idx, 1)
  else modes.push(mode)
  emit('updateProfile', { preferred_modes: modes.slice(0, 3) })
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-light);
  overflow: hidden;
}

.sidebar-top {
  padding: var(--space-lg) var(--space-md);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.logo-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--space-lg);
}
.logo-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-text {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.new-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 7px 12px;
  border-radius: var(--radius-sm);
  border: 1px dashed var(--border-medium);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.new-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
  min-height: 0;
}

.conv-item {
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: 2px;
  position: relative;
}
.conv-item:hover {
  background: var(--bg-hover);
}
.conv-item.active {
  background: var(--accent-soft);
}

.conv-title {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 16px;
}
.conv-item.active .conv-title {
  color: var(--text-primary);
}

.conv-del {
  position: absolute;
  right: 4px;
  top: 6px;
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 10px;
  padding: 2px 4px;
  border-radius: var(--radius-sm);
  display: none;
}
.conv-item:hover .conv-del {
  display: block;
}
.conv-del:hover {
  color: var(--danger);
}

.conv-empty {
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  padding: 30px 0;
}

.sidebar-bottom {
  padding: var(--space-md);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.mode-tags {
  display: flex;
  gap: 4px;
}
.mode-tag {
  padding: 3px 8px;
  border-radius: var(--radius-xl);
  font-size: var(--text-base);
  color: var(--text-tertiary);
  cursor: pointer;
  border: 1px solid var(--border-light);
  transition: all var(--duration-fast) var(--ease-out);
  line-height: 1.4;
}
.mode-tag.active {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

.sidebar-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-sm);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--danger);
  flex-shrink: 0;
  transition: background var(--duration-normal);
}
.dot.on {
  background: var(--success);
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.4);
}
.status {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
</style>
