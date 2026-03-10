'use client'

import { useSSEChat } from '@/hooks/useSSEChat'
import type { QuickButton } from '@/types/message'

export function QuickReplyButtons({ buttons }: { buttons: QuickButton[] }) {
  const { sendMessage, isStreaming } = useSSEChat()

  if (!buttons.length) return null

  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {buttons.map((btn, i) => (
        <button
          key={i}
          onClick={() => !isStreaming && sendMessage(btn.value)}
          disabled={isStreaming}
          className="rounded-full border border-primary-300 px-3 py-1.5 text-xs font-medium text-primary-600 transition-colors hover:bg-primary-50 disabled:opacity-50 dark:border-primary-600 dark:text-primary-400 dark:hover:bg-primary-900/20"
        >
          {btn.title}
        </button>
      ))}
    </div>
  )
}
