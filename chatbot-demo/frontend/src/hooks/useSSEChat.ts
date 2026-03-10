'use client'

import { useCallback } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { parseSSE } from '@/lib/sse-parser'
import type { ProgressStep, QuickButton } from '@/types/message'

const API_BASE = '/api/chat/stream'

export function useSSEChat() {
  const {
    activeConversationId,
    isStreaming,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    setProgress,
    addHtmlBlock,
    setButtons,
    finalizeMessage,
    setStreaming,
    createConversation,
  } = useChatStore()

  const sendMessage = useCallback(
    async (message: string) => {
      if (isStreaming) return

      let sessionId = activeConversationId
      if (!sessionId) {
        sessionId = createConversation()
      }

      addUserMessage(message)
      startAssistantMessage()
      setStreaming(true)

      try {
        const res = await fetch(API_BASE, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message,
            session_id: sessionId,
          }),
        })

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`)
        }

        const reader = res.body?.getReader()
        if (!reader) throw new Error('No readable stream')

        for await (const sseEvent of parseSSE(reader)) {
          try {
            const data = JSON.parse(sseEvent.data)

            switch (sseEvent.event) {
              case 'token':
                appendToken(data.content || '')
                break
              case 'progress':
                setProgress(data.steps as ProgressStep[])
                break
              case 'html':
                addHtmlBlock(data.content || '')
                break
              case 'buttons':
                setButtons(data.buttons as QuickButton[])
                break
              case 'done':
                finalizeMessage(data.answer)
                break
              case 'error':
                appendToken(`\n\n오류: ${data.message}`)
                finalizeMessage()
                break
            }
          } catch (parseErr) {
            console.warn('SSE parse error:', parseErr)
          }
        }
      } catch (err) {
        console.error('SSE connection error:', err)
        appendToken('\n\n연결 오류가 발생했습니다. 다시 시도해주세요.')
        finalizeMessage()
      } finally {
        setStreaming(false)
      }
    },
    [
      activeConversationId,
      isStreaming,
      addUserMessage,
      startAssistantMessage,
      appendToken,
      setProgress,
      addHtmlBlock,
      setButtons,
      finalizeMessage,
      setStreaming,
      createConversation,
    ]
  )

  return { sendMessage, isStreaming }
}
