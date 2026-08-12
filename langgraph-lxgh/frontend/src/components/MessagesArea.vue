<template>
  <n-layout-content class="chat-body">
    <n-scrollbar ref="scrollRef" class="scroll-area">
      <div class="msg-list">

        <!-- ========== 欢迎页面 ========== -->
        <div v-if="messages.length === 0 && !loading" class="welcome">
          <div class="welcome-bg"></div>
          <div class="welcome-content">
            <div class="welcome-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M2 12h20"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
            </div>
            <h1 class="welcome-title">路线规划智能体</h1>
            <p class="welcome-subtitle">输入出发地和目的地，我帮你规划最佳路线</p>
            <div class="welcome-suggestions">
              <button class="suggestion-chip" @click="$emit('suggest', '从北京到上海怎么走')">
                <span>🚗</span> 北京 → 上海
              </button>
              <button class="suggestion-chip" @click="$emit('suggest', '天安门附近有什么好吃的')">
                <span>🍜</span> 天安门附近美食
              </button>
              <button class="suggestion-chip" @click="$emit('suggest', '合肥到蚌埠有哪些火车票')">
                <span>🚄</span> 合肥 → 蚌埠火车
              </button>
              <button class="suggestion-chip" @click="$emit('suggest', '杭州西湖怎么去')">
                <span>🏞️</span> 杭州西湖路线
              </button>
            </div>
          </div>
        </div>

        <!-- ========== 消息列表 ========== -->
        <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
          <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="msg-body">
            <div class="msg-bubble" v-html="msg.content"></div>
            <div class="msg-time">{{ msg.time }}</div>
          </div>
        </div>

        <!-- ========== 骨架屏加载态 ========== -->
        <div v-if="loading" class="skeleton">
          <div class="skeleton-avatar"></div>
          <div class="skeleton-lines">
            <div class="skeleton-line" style="width: 65%;"></div>
            <div class="skeleton-line" style="width: 85%;"></div>
            <div class="skeleton-line" style="width: 40%;"></div>
          </div>
        </div>

        <!-- ========== 路线选择卡片 ========== -->
        <div v-if="routeSel" class="route-box">
          <div class="route-box-title">📌 选择路线</div>
          <div
            v-for="r in routeSel.routes"
            :key="r.id"
            class="route-item"
            :class="{ recommended: r.id === routeSel.recommended_id }"
            @click="$emit('selectRoute', r.id)">
            <div v-if="r.id === routeSel.recommended_id" class="rec-tag">推荐</div>
            <div v-if="r.type === 'route'">
              <div class="ri-top">{{ modeIcon(r.mode) }} {{ r.mode_label || r.mode }}</div>
              <div class="ri-summary">{{ r.summary }}</div>
              <div class="ri-meta">
                <span>📏 {{ fmtDist(r.distance) }}</span>
                <span>⏱️ {{ fmtDur(r.duration) }}</span>
                <span v-if="r.tolls > 0">💰 {{ r.tolls }}元</span>
              </div>
              <div class="ri-actions">
                <n-button text size="tiny" @click.stop="$emit('openMap', r)">
                  🗺️ 查看地图
                </n-button>
                <n-button text size="tiny" @click.stop="$emit('fillRoute', r)">
                  ✏️ 修改
                </n-button>
              </div>
            </div>
            <div v-else class="poi-card">
              <div class="poi-icon">📍</div>
              <div class="poi-info">
                <div class="poi-name">{{ r.name }}</div>
                <div class="poi-addr">{{ r.address }}</div>
                <div class="poi-meta">
                  <span v-if="r.distance">距 {{ r.distance }}m</span>
                  <span v-if="r.rating" style="margin-left:8px;">⭐ {{ r.rating }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div style="height:16px;"></div>
      </div>
    </n-scrollbar>
  </n-layout-content>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  messages: Array,
  loading: Boolean,
  routeSel: Object,
})

const emit = defineEmits(['selectRoute', 'openMap', 'fillRoute', 'suggest'])

const scrollRef = ref(null)

const modeIcon = (m) =>
  ({ car: '🚗', walk: '🚶', ride: '🚲', bus: '🚌' }[m] || '🚗')
const fmtDist = (m) =>
  m >= 1000 ? `${(m / 1000).toFixed(1)} 公里` : `${m} 米`
const fmtDur = (s) => {
  const mi = Math.floor(s / 60)
  const h = Math.floor(mi / 60)
  return h > 0 ? `${h} 小时 ${mi % 60} 分钟` : `${mi} 分钟`
}

watch(
  () => props.messages?.length,
  () => {
    nextTick(() => {
      const el = scrollRef.value?.$el || scrollRef.value
      el?.scrollTo?.({ top: el.scrollHeight, behavior: 'smooth' })
    })
  }
)
</script>

<style scoped>
.chat-body {
  background: transparent !important;
}
.scroll-area {
  height: 100%;
}
.msg-list {
  padding: var(--space-xl) var(--space-2xl);
  max-width: var(--chat-max-width);
  margin: 0 auto;
}

/* ===== 欢迎页 ===== */
.welcome {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 200px);
  overflow: hidden;
}
.welcome-bg {
  position: absolute;
  inset: -50%;
  background:
    radial-gradient(ellipse at 30% 40%, rgba(64, 158, 255, 0.04) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 60%, rgba(129, 140, 248, 0.03) 0%, transparent 50%);
  animation: bgFloat 20s ease-in-out infinite alternate;
}
@keyframes bgFloat {
  from { transform: translate(0, 0) rotate(0deg); }
  to   { transform: translate(2%, 1%) rotate(2deg); }
}
.welcome-content {
  position: relative;
  text-align: center;
  padding: 40px 20px;
}
.welcome-icon {
  color: var(--accent);
  opacity: 0.6;
  margin-bottom: var(--space-lg);
  animation: pulseGlow 3s ease-in-out infinite;
}
@keyframes pulseGlow {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50%      { opacity: 0.8; transform: scale(1.05); }
}
.welcome-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
  letter-spacing: -0.02em;
}
.welcome-subtitle {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin-bottom: var(--space-2xl);
}
.welcome-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  justify-content: center;
  max-width: 480px;
  margin: 0 auto;
}
.suggestion-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-light);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.suggestion-chip:hover {
  border-color: var(--accent);
  color: var(--text-primary);
  background: var(--accent-soft);
  transform: translateY(-1px);
}
.suggestion-chip span {
  font-size: var(--text-lg);
}

/* ===== 消息气泡 ===== */
.msg {
  display: flex;
  gap: 10px;
  margin-bottom: var(--space-xl);
  animation: fadeIn 0.25s var(--ease-out);
  position: relative;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.msg.user {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  background: var(--bg-hover);
}
.msg-body {
  max-width: 72%;
  min-width: 0;
}
.msg.user .msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.msg-bubble {
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  line-height: 1.7;
  overflow-wrap: break-word;
}
.assistant .msg-bubble {
  background: var(--bg-surface);
  color: var(--text-primary);
  border-bottom-left-radius: var(--radius-sm);
}
.user .msg-bubble {
  background: var(--accent-gradient);
  color: #fff;
  border-bottom-right-radius: var(--radius-sm);
}
.msg-time {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
  padding: 0 var(--space-xs);
}
.user .msg-time {
  text-align: right;
}

/* Markdown 样式 */
.msg-bubble :deep(p) { margin: 6px 0; }
.msg-bubble :deep(p:first-child) { margin-top: 0; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(code) {
  background: var(--bg-hover);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.9em;
  font-family: var(--font-mono);
}
.msg-bubble :deep(pre) {
  background: rgba(0, 0, 0, 0.25);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  overflow-x: auto;
}
.msg-bubble :deep(a) {
  color: var(--accent);
  text-decoration: none;
}
.msg-bubble :deep(ul),
.msg-bubble :deep(ol) {
  padding-left: 18px;
}
.msg-bubble :deep(li) {
  margin: 3px 0;
}
.msg-bubble :deep(blockquote) {
  border-left: 2px solid var(--accent-soft);
  padding-left: 10px;
  color: var(--text-secondary);
}
.msg-bubble :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.msg-bubble :deep(th),
.msg-bubble :deep(td) {
  border: 1px solid var(--border-light);
  padding: 6px 10px;
}
.msg-bubble :deep(.msg-info) {
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}
.msg-bubble :deep(.msg-error) {
  color: var(--danger);
}

/* ===== 骨架屏 ===== */
.skeleton {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  animation: fadeIn 0.25s var(--ease-out);
}
.skeleton-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--bg-elevated);
  flex-shrink: 0;
  animation: shimmer 1.5s ease-in-out infinite;
}
.skeleton-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 6px;
}
.skeleton-line {
  height: 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  animation: shimmer 1.5s ease-in-out infinite;
}
.skeleton-line:nth-child(2) {
  animation-delay: 0.1s;
}
.skeleton-line:nth-child(3) {
  animation-delay: 0.2s;
}
@keyframes shimmer {
  0%   { opacity: 0.4; }
  50%  { opacity: 0.8; }
  100% { opacity: 0.4; }
}

/* ===== 路线卡片 ===== */
.route-box {
  margin-bottom: var(--space-lg);
  animation: fadeIn 0.25s var(--ease-out);
}
.route-box-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}
.route-item {
  position: relative;
  padding: var(--space-lg);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: var(--space-sm);
}
.route-item:hover {
  background: var(--accent-soft);
  border-color: rgba(64, 158, 255, 0.2);
  transform: translateY(-1px);
}
.route-item.recommended {
  border-color: rgba(103, 194, 58, 0.3);
  background: rgba(103, 194, 58, 0.04);
}
.rec-tag {
  position: absolute;
  top: -7px;
  right: 12px;
  padding: 1px 10px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--success), var(--accent));
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}
.ri-top {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
}
.ri-summary {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}
.ri-meta {
  display: flex;
  gap: var(--space-md);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.ri-actions {
  display: flex;
  gap: var(--space-md);
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-light);
}
.ri-actions :deep(.n-button) {
  color: var(--accent) !important;
  font-size: var(--text-sm) !important;
}

/* POI 卡片 */
.poi-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}
.poi-icon {
  font-size: 24px;
  flex-shrink: 0;
}
.poi-name {
  font-weight: 600;
  color: var(--text-primary);
}
.poi-addr {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.poi-meta {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}
</style>
