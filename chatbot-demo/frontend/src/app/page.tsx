'use client'

import { AppLayout } from '@/components/layout/AppLayout'
import { MessageList } from '@/components/chat/MessageList'
import { ChatInput } from '@/components/chat/ChatInput'

export default function Home() {
  return (
    <AppLayout>
      <div className="flex h-full flex-col">
        <MessageList />
        <ChatInput />
      </div>
    </AppLayout>
  )
}
