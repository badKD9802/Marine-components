'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function MarkdownContent({ content }: { content: string }) {
  if (!content) return null

  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-li:my-0 prose-headings:mb-2 prose-headings:mt-4">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
