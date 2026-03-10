'use client'

import { Plus, MessageSquare, Trash2, X } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useUIStore } from '@/stores/uiStore'

export function Sidebar() {
  const { conversations, activeConversationId, createConversation, setActiveConversation, deleteConversation } = useChatStore()
  const { sidebarOpen, setSidebarOpen } = useUIStore()

  const handleNew = () => {
    setActiveConversation(null)
  }

  // 날짜별 그룹핑
  const grouped = groupByDate(conversations)

  return (
    <>
      {/* 모바일 오버레이 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed left-0 top-0 z-30 flex h-full w-[280px] flex-col border-r border-gray-200 bg-[var(--sidebar-bg)] transition-transform duration-300 dark:border-gray-700 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 p-4 dark:border-gray-700">
          <h1 className="text-lg font-semibold text-primary-600">AI Assistant</h1>
          <button
            onClick={() => setSidebarOpen(false)}
            className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 md:hidden dark:hover:bg-gray-700"
          >
            <X size={20} />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={handleNew}
            className="flex w-full items-center gap-2 rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            <Plus size={18} />
            새 대화
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto px-3 pb-3">
          {grouped.map(([label, convs]) => (
            <div key={label} className="mb-3">
              <p className="mb-1 px-2 text-xs font-medium text-gray-400">{label}</p>
              {convs.map(conv => (
                <button
                  key={conv.id}
                  onClick={() => {
                    setActiveConversation(conv.id)
                    setSidebarOpen(false)
                  }}
                  className={`group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                    conv.id === activeConversationId
                      ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700'
                  }`}
                >
                  <MessageSquare size={16} className="shrink-0" />
                  <span className="flex-1 truncate">{conv.title}</span>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      deleteConversation(conv.id)
                    }}
                    className="hidden shrink-0 rounded p-1 text-gray-400 hover:text-red-500 group-hover:block"
                  >
                    <Trash2 size={14} />
                  </button>
                </button>
              ))}
            </div>
          ))}
        </div>
      </aside>
    </>
  )
}

function groupByDate(conversations: { id: string; title: string; updatedAt: number }[]) {
  const now = Date.now()
  const day = 86400000
  const groups: Record<string, typeof conversations> = {}

  for (const conv of conversations) {
    const diff = now - conv.updatedAt
    let label: string
    if (diff < day) label = '오늘'
    else if (diff < 2 * day) label = '어제'
    else if (diff < 7 * day) label = '이번 주'
    else label = '이전'

    if (!groups[label]) groups[label] = []
    groups[label].push(conv)
  }

  const order = ['오늘', '어제', '이번 주', '이전']
  return order.filter(l => groups[l]).map(l => [l, groups[l]] as const)
}
