import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation } from '../utils/conversationStore'
import {
  loadConversations,
  saveConversations,
  loadActiveId,
  saveActiveId,
} from '../utils/conversationStore'

export const useWorkbenchSidebarStore = defineStore('workbenchSidebar', () => {
  const conversations = ref<Conversation[]>([])
  const activeConversationId = ref('')
  const activeMode = ref<'direct' | 'make' | 'voice'>('direct')
  const sidebarCollapsed = ref(false)

  const activeConversation = computed(() =>
    conversations.value.find((c) => c.id === activeConversationId.value) ?? null,
  )

  function initConversations() {
    try {
      conversations.value = loadConversations()
      const storedActive = loadActiveId()
      if (storedActive && conversations.value.some((c) => c.id === storedActive)) {
        activeConversationId.value = storedActive
      } else if (conversations.value.length) {
        activeConversationId.value = conversations.value[0].id
        saveActiveId(activeConversationId.value)
      }
    } catch {
      /* ignore */
    }
  }

  function persistConversations() {
    saveConversations(conversations.value)
  }

  function pickConversation(id: string) {
    if (id === activeConversationId.value) return
    activeConversationId.value = id
    saveActiveId(id)
  }

  function removeConversation(id: string) {
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (activeConversationId.value === id) {
      activeConversationId.value = conversations.value[0]?.id || ''
      saveActiveId(activeConversationId.value)
    }
    persistConversations()
  }

  function setActiveMode(mode: 'direct' | 'make' | 'voice') {
    activeMode.value = mode
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function updateConversation(id: string, patch: Partial<Conversation>) {
    conversations.value = conversations.value.map((c) =>
      c.id === id ? { ...c, ...patch, updatedAt: Date.now() } : c,
    )
    persistConversations()
  }

  function setConversations(list: Conversation[]) {
    conversations.value = list
    persistConversations()
  }

  function setActiveConversationId(id: string) {
    activeConversationId.value = id
    saveActiveId(id)
  }

  return {
    conversations,
    activeConversationId,
    activeConversation,
    activeMode,
    sidebarCollapsed,
    initConversations,
    persistConversations,
    pickConversation,
    removeConversation,
    setActiveMode,
    toggleSidebar,
    updateConversation,
    setConversations,
    setActiveConversationId,
  }
})
