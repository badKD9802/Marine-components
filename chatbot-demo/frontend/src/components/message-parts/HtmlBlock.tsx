'use client'

import { sanitizeHtml } from '@/lib/sanitize'

export function HtmlBlock({ html }: { html: string }) {
  if (!html || !html.trim()) return null

  const clean = sanitizeHtml(html)

  return (
    <div
      className="html-block overflow-x-auto rounded-lg border border-gray-200 bg-white p-4 text-sm dark:border-gray-600 dark:bg-gray-800"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
}
