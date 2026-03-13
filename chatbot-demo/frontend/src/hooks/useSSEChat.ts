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

      // 초기 progress 표시 (백엔드에서 실제 progress 오면 덮어씀)
      setProgress([{ title: '질문을 분석하고 있습니다...', status: 'active' as const }])

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
                console.log('[SSE] progress event:', JSON.stringify(data))
                if (Array.isArray(data.steps)) {
                  setProgress(data.steps as ProgressStep[])
                } else if (Array.isArray(data)) {
                  setProgress(data as ProgressStep[])
                }
                break
              case 'html':
                if (data.content) {
                  addHtmlBlock(data.content)
                }
                break
              case 'buttons':
                if (Array.isArray(data.buttons)) {
                  setButtons(data.buttons as QuickButton[])
                } else if (Array.isArray(data)) {
                  setButtons(data as QuickButton[])
                }
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
        // 안전장치: done 이벤트 누락 시에도 progress step을 completed로 전환
        finalizeMessage()
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
