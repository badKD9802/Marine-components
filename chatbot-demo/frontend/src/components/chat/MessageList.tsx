'use client'

import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { UserMessage } from './UserMessage'
import { AssistantMessage } from './AssistantMessage'
import { WelcomeScreen } from './WelcomeScreen'

export function MessageList() {
  const conv = useChatStore(s =>
    s.conversations.find(c => c.id === s.activeConversationId)
  )
  const isStreaming = useChatStore(s => s.isStreaming)
  const bottomRef = useRef<HTMLDivElement>(null)

  const messages = conv?.messages || []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, isStreaming])

  if (messages.length === 0) {
    return <WelcomeScreen />
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-4xl space-y-6">
        {messages.map(msg =>
          msg.role === 'user' ? (
            <UserMessage key={msg.id} message={msg} />
          ) : (
            <AssistantMessage key={msg.id} message={msg} />
          )
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
