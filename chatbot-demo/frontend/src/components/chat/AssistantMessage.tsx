import { Bot } from 'lucide-react'
import type { Message } from '@/types/message'
import { ProgressSteps } from '../message-parts/ProgressSteps'
import { HtmlBlock } from '../message-parts/HtmlBlock'
import { MarkdownContent } from '../message-parts/MarkdownContent'
import { QuickReplyButtons } from '../message-parts/QuickReplyButtons'
import { TemplateSelector } from '../message-parts/TemplateSelector'
import { ExampleSelector } from '../message-parts/ExampleSelector'
import { DocumentPreview } from '../message-parts/DocumentPreview'

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
                case 'template_selector':
                  return <TemplateSelector key={i} candidates={part.templateCandidates || []} />
                case 'example_selector':
                  return (
                    <ExampleSelector
                      key={i}
                      templateTitle={part.templateTitle || ''}
                      examples={part.examples || []}
                    />
                  )
                case 'document_preview':
                  return part.documentPreview ? (
                    <DocumentPreview key={i} {...part.documentPreview} />
                  ) : null
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
