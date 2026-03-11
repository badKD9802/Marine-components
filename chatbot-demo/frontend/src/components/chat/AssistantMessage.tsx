import { Bot } from 'lucide-react'
import type { Message } from '@/types/message'
import { ProgressSteps } from '../message-parts/ProgressSteps'
import { HtmlBlock } from '../message-parts/HtmlBlock'
import { MarkdownContent } from '../message-parts/MarkdownContent'
import { QuickReplyButtons } from '../message-parts/QuickReplyButtons'

export function AssistantMessage({ message }: { message: Message }) {
  return (
    <div className="flex justify-start">
      <div className="flex-1 min-w-0 space-y-3">
        {/* 아바타 */}
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/50">
            <Bot size={18} className="text-primary-600 dark:text-primary-300" />
          </div>
          <div className="space-y-2 pt-1">
            {message.parts.map((part, i) => {
              switch (part.type) {
                case 'progress':
                  return (
                    <ProgressSteps
                      key={i}
                      steps={part.steps || []}
                      isStreaming={message.isStreaming}
                    />
                  )
                case 'html':
                  return <HtmlBlock key={i} html={part.content || ''} />
                case 'text':
                  return (
                    <div
                      key={i}
                      className={message.isStreaming ? 'streaming-cursor' : ''}
                    >
                      <MarkdownContent content={part.content || ''} />
                    </div>
                  )
                case 'buttons':
                  return <QuickReplyButtons key={i} buttons={part.buttons || []} />
                default:
                  return null
              }
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
