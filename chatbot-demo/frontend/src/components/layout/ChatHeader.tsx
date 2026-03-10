'use client'

import { Menu, Moon, Sun } from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useChatStore } from '@/stores/chatStore'

export function ChatHeader() {
  const { toggleSidebar, darkMode, toggleDarkMode } = useUIStore()
  const activeConversation = useChatStore(s => s.activeConversation)
  const conv = activeConversation()

  return (
    <header className="flex items-center justify-between border-b border-gray-200 bg-[var(--chat-bg)] px-4 py-3 dark:border-gray-700">
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
        >
          <Menu size={20} />
        </button>
        <div>
          <h2 className="text-sm font-medium text-gray-800 dark:text-gray-200">
            {conv?.title || 'AI Assistant'}
          </h2>
          <span className="text-xs text-gray-400">GPT-4o · ReAct Agent</span>
        </div>
      </div>

      <button
        onClick={toggleDarkMode}
        className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        {darkMode ? <Sun size={18} /> : <Moon size={18} />}
      </button>
    </header>
  )
}
