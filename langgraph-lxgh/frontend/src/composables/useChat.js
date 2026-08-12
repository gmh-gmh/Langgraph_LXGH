/**
 * useChat.js — 对话状态管理组合式函数
 *
 * 从 App.vue 提取的所有对话逻辑：
 * - 会话 CRUD + localStorage 持久化
 * - SSE 流式消息发送/接收
 * - 用户画像管理
 * - 路线选择
 * - 图片上传
 */
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { marked } from 'marked'  // Markdown → HTML 渲染库

const CONV_KEY = 'route_conversations'      // 会话列表的 localStorage key
const PROFILE_KEY = 'route_user_profile'     // 用户画像的 key
const USER_ID_KEY = 'route_user_id'          // 用户 ID 的 key

/* ========== 存储工具 ========== */
function loadFrom(key, fallback) {
  try {
    const r = localStorage.getItem(key)
    return r ? JSON.parse(r) : fallback
  } catch {
    return fallback
  }
}

function saveTo(key, val) {
  try {
    if (val != null) localStorage.setItem(key, JSON.stringify(val))
    else localStorage.removeItem(key)
  } catch { /* silent */ }
}

/* ========== Composable ========== */
export function useChat() {
  /* ---- 响应式状态 ---- */
  const conversations = ref(loadFrom(CONV_KEY, []))
  const currentConvId = ref(
    conversations.value.length > 0 ? conversations.value[0].id : null
  )
  const isLoading = ref(false)
  const wsConnected = ref(true)
  const selectedImage = ref(null)
  const imageInput = ref(null)

  const userId = ref(loadFrom(USER_ID_KEY, 'user_' + Date.now().toString(36)))
  const userProfile = ref(
    loadFrom(PROFILE_KEY, { preferred_modes: [], trip_preferences: {} })
  )

  /* ---- 计算属性 ---- */
  const currentMessages = computed(() => {
    const conv = conversations.value.find(c => c.id === currentConvId.value)
    return conv ? conv.messages : []
  })

  const currentTitle = computed(() => {
    const conv = conversations.value.find(c => c.id === currentConvId.value)
    return conv ? conv.title : '新对话'
  })

  const hasConversations = computed(() => conversations.value.length > 0)
  const isEmpty = computed(() => currentMessages.value.length === 0)

  /* ---- 持久化 ---- */
  function saveConversations() {
    saveTo(CONV_KEY, conversations.value)
  }
  watch(conversations, saveConversations, { deep: true })
  watch(userId, () => saveTo(USER_ID_KEY, userId.value))
  watch(() => userProfile.value, () => saveTo(PROFILE_KEY, userProfile.value), {
    deep: true,
  })

  /* ---- 会话管理 ---- */
  function createConversation(title) {
    const id = 'conv_' + Date.now().toString(36)
    const conv = {
      id,
      title: title || '新对话',
      sessionId: null,
      messages: [],
      time: new Date().toISOString(),
    }
    conversations.value.unshift(conv)
    currentConvId.value = id
    return conv
  }

  function startNewChat() {
    createConversation()
    selectedImage.value = null
  }

  function switchConversation(id) {
    currentConvId.value = id
  }

  function deleteConversation(id) {
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx === -1) return
    conversations.value.splice(idx, 1)
    if (currentConvId.value === id) {
      currentConvId.value =
        conversations.value.length > 0 ? conversations.value[0].id : null
    }
  }

  function getCurrentConv() {
    return conversations.value.find(c => c.id === currentConvId.value)
  }

  const getTime = () => {
    const d = new Date()
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  function addMsg(role, content) {
    const conv = getCurrentConv()
    if (!conv) return
    conv.messages.push({
      role,
      content: typeof content === 'string' && role === 'user'
        ? content
        : content,
      time: getTime(),
    })
  }

  /* ---- 图片上传 ---- */
  function triggerUpload() {
    imageInput.value?.click()
  }

  function onFileSelected(e) {
    const f = e.target.files[0]
    if (!f) return
    const r = new FileReader()
    r.onload = ev => {
      selectedImage.value = ev.target.result
    }
    r.readAsDataURL(f)
  }

  function removeImage() {
    selectedImage.value = null
    if (imageInput.value) imageInput.value.value = ''
  }

  /* ---- 高德地图 ---- */
  function openAmapRoute(route) {
    if (route.map_url) {
      window.open(route.map_url, '_blank')
      return
    }
    const modeMap = { car: 'car', walk: 'walk', ride: 'ride', bus: 'bus' }
    const t = modeMap[route.mode] || 'car'
    const [ol, olat] = (route.origin_coord || '116.397,39.908').split(',')
    const [dl, dlat] = (route.dest_coord || '121.473,31.230').split(',')
    const on = encodeURIComponent(route.origin_name || '起点')
    const dn = encodeURIComponent(route.dest_name || '终点')
    window.open(
      `https://ditu.amap.com/dir?from%5Bname%5D=${on}&from%5Blng%5D=${ol}&from%5Blat%5D=${olat}&to%5Bname%5D=${dn}&to%5Blng%5D=${dl}&to%5Blat%5D=${dlat}&type=${t}`,
      '_blank'
    )
  }

  /* ---- 发送消息（SSE 流式） ---- */
  let lastAssistantMsg = -1

  async function handleSend(text) {
    if (!text?.trim() && !selectedImage.value) return
    const query = text?.trim() || ''
    const base64 = selectedImage.value
      ? selectedImage.value.split(',')[1]
      : null

    let conv = getCurrentConv()
    if (!conv) conv = createConversation()
    if (conv.messages.length === 0)
      conv.title = query.slice(0, 20) + (query.length > 20 ? '...' : '')

    addMsg('user', query || '[图片]')
    selectedImage.value = null
    isLoading.value = true
    lastAssistantMsg = -1

    try {
      const resp = await fetch('/api/multi/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_query: query,
          image_base64: base64,
          session_id: conv.sessionId,
          user_id: userId.value,
        }),
      })
      if (!resp.ok) throw new Error('请求失败 (' + resp.status + ')')

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      let full = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        while (buf.includes('\n\n')) {
          const [event, rest] = buf.split('\n\n', 2)
          buf = rest
          if (!event.startsWith('data: ')) continue
          try {
            const data = JSON.parse(event.slice(6))
            switch (data.type) {
              case 'info':
                conv.messages.push({
                  role: 'assistant',
                  content: `<div class="msg-info">${data.content}</div>`,
                  time: getTime(),
                })
                break
              case 'stream':
                full += data.content
                if (lastAssistantMsg === -1) {
                  conv.messages.push({
                    role: 'assistant',
                    content: marked.parse(full),
                    time: getTime(),
                  })
                  lastAssistantMsg = conv.messages.length - 1
                } else {
                  conv.messages[lastAssistantMsg].content = marked.parse(full)
                }
                break
              case 'end':
                if (data.session_id) conv.sessionId = data.session_id
                isLoading.value = false
                break
              case 'error':
                conv.messages.push({
                  role: 'assistant',
                  content: `<div class="msg-error">${data.content}</div>`,
                  time: getTime(),
                })
                isLoading.value = false
                break
            }
          } catch (e) {
            console.error('SSE error:', e)
          }
        }
      }
    } catch (err) {
      conv.messages.push({
        role: 'assistant',
        content: `<div class="msg-error">❌ 请求失败: ${err.message}</div>`,
        time: getTime(),
      })
    } finally {
      isLoading.value = false
    }
  }

  /* ---- 路线选择 ---- */
  async function selectRoute(id) {
    const conv = getCurrentConv()
    if (!conv || !conv.sessionId) return
    isLoading.value = true
    try {
      const resp = await fetch('/api/select-route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: conv.sessionId,
          selected_route_id: id,
        }),
      })
      const result = await resp.json()
      if (result.response) addMsg('assistant', result.response)
    } catch (err) {
      conv.messages.push({
        role: 'assistant',
        content: `<div class="msg-error">❌ 选择失败: ${err.message}</div>`,
        time: getTime(),
      })
    } finally {
      isLoading.value = false
    }
  }

  /* ---- 用户画像 ---- */
  async function loadProfile() {
    try {
      const resp = await fetch(
        `/api/profile/${encodeURIComponent(userId.value)}`
      )
      if (resp.ok) {
        const d = await resp.json()
        if (d.profile) userProfile.value = d.profile
      }
    } catch { /* offline */ }
  }

  function updateProfile(updates) {
    if (updates.preferred_modes)
      userProfile.value.preferred_modes = updates.preferred_modes
    if (updates.trip_preferences)
      userProfile.value.trip_preferences = {
        ...(userProfile.value.trip_preferences || {}),
        ...updates.trip_preferences,
      }
    if (updates.ev_car !== undefined)
      userProfile.value.ev_car = updates.ev_car
    // 异步发送到后端
    fetch(`/api/profile/${encodeURIComponent(userId.value)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }).catch(() => { /* silent */ })
  }

  /* ---- 生命周期 ---- */
  onMounted(() => {
    saveTo(USER_ID_KEY, userId.value)
    loadProfile()
    if (conversations.value.length === 0) createConversation()
  })

  /* ---- 暴露给组件的 API ---- */
  return {
    // 状态
    conversations,
    currentConvId,
    isLoading,
    wsConnected,
    selectedImage,
    imageInput,
    userId,
    userProfile,
    // 计算属性
    currentMessages,
    currentTitle,
    hasConversations,
    isEmpty,
    // 方法
    startNewChat,
    switchConversation,
    deleteConversation,
    handleSend,
    selectRoute,
    openAmapRoute,
    triggerUpload,
    onFileSelected,
    removeImage,
    updateProfile,
  }
}
