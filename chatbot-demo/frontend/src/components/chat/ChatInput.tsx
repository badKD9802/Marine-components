'use client'

import { useState, useRef, useCallback, KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'

export function ChatInput() {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { sendMessage, isStreaming } = useSSEChat()

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    sendMessage(trimmed)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isStreaming, sendMessage])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 200) + 'px'
    }
  }

  return (
    <div className="border-t border-gray-200 bg-[var(--chat-bg)] px-4 py-3 dark:border-gray-700">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => {
              setInput(e.target.value)
              handleInput()
            }}
            onKeyDown={handleKeyDown}
            placeholder="메시지를 입력하세요..."
            rows={1}
            className="w-full resize-none rounded-xl border border-gray-300 bg-white px-4 py-3 pr-12 text-sm outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
            disabled={isStreaming}
          />
        </div>
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isStreaming}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-600 text-white transition-colors hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Send size={18} />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-gray-400">
        AI 응답은 데모 목적이며, 실제 데이터와 다를 수 있습니다.
      </p>
    </div>
  )
}
