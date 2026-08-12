<template>
  <n-config-provider :theme="darkTheme">
    <n-message-provider>
      <div class="app-root">
        <ChatSidebar
          :connected="wsConnected"
          :conversations="conversations"
          :currentConvId="currentConvId"
          :profile="userProfile"
          @newChat="startNewChat"
          @switchConv="switchConversation"
          @deleteConv="deleteConversation"
          @updateProfile="updateProfile" />

        <div class="chat-area">
          <ChatHeader :title="currentTitle" @uploadImg="triggerUpload" />

          <MessagesArea
            :messages="currentMessages"
            :loading="isLoading"
            @selectRoute="selectRoute"
            @openMap="openAmapRoute"
            @suggest="handleSuggest" />

          <ChatInput
            :loading="isLoading"
            :image="selectedImage"
            @send="handleSend"
            @removeImg="removeImage" />
        </div>

        <input
          ref="imageInput"
          type="file"
          accept="image/*"
          style="display:none"
          @change="onFileSelected" />
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { darkTheme } from 'naive-ui'
import { useChat } from './composables/useChat.js'

import ChatSidebar from './components/ChatSidebar.vue'
import ChatHeader from './components/ChatHeader.vue'
import MessagesArea from './components/MessagesArea.vue'
import ChatInput from './components/ChatInput.vue'

const {
  conversations,
  currentConvId,
  isLoading,
  wsConnected,
  selectedImage,
  imageInput,
  userProfile,
  currentMessages,
  currentTitle,
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
} = useChat()

function handleSuggest(text) {
  handleSend(text)
}
</script>

<style scoped>
.app-root {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-app);
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
</style>
