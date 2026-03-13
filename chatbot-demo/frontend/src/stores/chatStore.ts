import { create } from 'zustand'
import type { Conversation, Message, MessagePart, ProgressStep, QuickButton } from '@/types/message'

interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  isStreaming: boolean

  // Getters
  activeConversation: () => Conversation | undefined

  // Actions
  createConversation: (id?: string) => string
  setActiveConversation: (id: string | null) => void
  deleteConversation: (id: string) => void
  addUserMessage: (content: string) => void
  startAssistantMessage: () => void
  appendToken: (token: string) => void
  setProgress: (steps: ProgressStep[]) => void
  addHtmlBlock: (html: string) => void
  setButtons: (buttons: QuickButton[]) => void
  finalizeMessage: (fullAnswer?: string) => void
  setStreaming: (streaming: boolean) => void
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2)
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  isStreaming: false,

  activeConversation: () => {
    const state = get()
    return state.conversations.find(c => c.id === state.activeConversationId)
  },

  createConversation: (id?: string) => {
    const convId = id || generateId()
    const conv: Conversation = {
      id: convId,
      title: '새 대화',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    set(state => ({
      conversations: [conv, ...state.conversations],
      activeConversationId: convId,
    }))
    return convId
  },

  setActiveConversation: (id: string | null) => {
    set({ activeConversationId: id })
  },

  deleteConversation: (id: string) => {
    set(state => {
      const filtered = state.conversations.filter(c => c.id !== id)
      return {
        conversations: filtered,
        activeConversationId:
          state.activeConversationId === id
            ? filtered[0]?.id || null
            : state.activeConversationId,
      }
    })
  },

  addUserMessage: (content: string) => {
    const msg: Message = {
      id: generateId(),
      role: 'user',
      parts: [{ type: 'text', content }],
      timestamp: Date.now(),
    }
    set(state => ({
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        const title = c.messages.length === 0
          ? content.slice(0, 30) + (content.length > 30 ? '...' : '')
          : c.title
        return {
          ...c,
          title,
          messages: [...c.messages, msg],
          updatedAt: Date.now(),
        }
      }),
    }))
  },

  startAssistantMessage: () => {
    const msg: Message = {
      id: generateId(),
      role: 'assistant',
      parts: [],
      timestamp: Date.now(),
      isStreaming: true,
    }
    set(state => ({
      isStreaming: true,
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        return { ...c, messages: [...c.messages, msg], updatedAt: Date.now() }
      }),
    }))
  },

  appendToken: (token: string) => {
    set(state => ({
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        const msgs = [...c.messages]
        const last = msgs[msgs.length - 1]
        if (!last || last.role !== 'assistant') return c

        const parts = [...last.parts]
        const lastPart = parts[parts.length - 1]
        if (lastPart && lastPart.type === 'text') {
          parts[parts.length - 1] = { ...lastPart, content: (lastPart.content || '') + token }
        } else {
          parts.push({ type: 'text', content: token })
        }
        msgs[msgs.length - 1] = { ...last, parts }
        return { ...c, messages: msgs }
      }),
    }))
  },

  setProgress: (steps: ProgressStep[]) => {
    set(state => ({
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        const msgs = [...c.messages]
        const last = msgs[msgs.length - 1]
        if (!last || last.role !== 'assistant') return c

        const parts = [...last.parts]
        const progressIdx = parts.findIndex(p => p.type === 'progress')
        if (progressIdx >= 0) {
          parts[progressIdx] = { type: 'progress', steps }
        } else {
          parts.push({ type: 'progress', steps })
        }
        msgs[msgs.length - 1] = { ...last, parts }
        return { ...c, messages: msgs }
      }),
    }))
  },

  addHtmlBlock: (html: string) => {
    set(state => ({
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        const msgs = [...c.messages]
        const last = msgs[msgs.length - 1]
        if (!last || last.role !== 'assistant') return c

        const parts = [...last.parts, { type: 'html' as const, content: html }]
        msgs[msgs.length - 1] = { ...last, parts }
        return { ...c, messages: msgs }
      }),
    }))
  },

  setButtons: (buttons: QuickButton[]) => {
    set(state => ({
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        const msgs = [...c.messages]
        const last = msgs[msgs.length - 1]
        if (!last || last.role !== 'assistant') return c

        const parts = [...last.parts, { type: 'buttons' as const, buttons }]
        msgs[msgs.length - 1] = { ...last, parts }
        return { ...c, messages: msgs }
      }),
    }))
  },

  finalizeMessage: (fullAnswer?: string) => {
    set(state => ({
      isStreaming: false,
      conversations: state.conversations.map(c => {
        if (c.id !== state.activeConversationId) return c
        const msgs = [...c.messages]
        const last = msgs[msgs.length - 1]
        if (!last || last.role !== 'assistant') return c
        // progress step 중 active/running 남아있으면 completed로 전환
        const parts = last.parts.map(part => {
          if (part.type !== 'progress' || !part.steps) return part
          const steps = part.steps.map(s =>
            s.status === 'active' || s.status === 'running'
              ? { ...s, status: 'completed' as const }
              : s
          )
          return { ...part, steps }
        })
        msgs[msgs.length - 1] = { ...last, parts, isStreaming: false }
        return { ...c, messages: msgs }
      }),
    }))
  },

  setStreaming: (streaming: boolean) => {
    set({ isStreaming: streaming })
  },
}))
