import type { Message } from '@/types/message'
import { ProgressSteps } from '../message-parts/ProgressSteps'
import { HtmlBlock } from '../message-parts/HtmlBlock'
import { MarkdownContent } from '../message-parts/MarkdownContent'
import { QuickReplyButtons } from '../message-parts/QuickReplyButtons'

export function AssistantMessage({ message }: { message: Message }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-3">
        {/* 아바타 */}
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-sm font-bold text-primary-700 dark:bg-primary-900 dark:text-primary-300">
            AI
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
