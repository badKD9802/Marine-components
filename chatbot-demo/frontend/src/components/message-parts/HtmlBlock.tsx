'use client'

import { useRef, useEffect } from 'react'

export function HtmlBlock({ html }: { html: string }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || !html) return
    containerRef.current.innerHTML = html
  }, [html])

  if (!html || !html.trim()) return null

  return (
    <div
      ref={containerRef}
      className="html-block overflow-x-auto rounded-lg border border-gray-200 bg-white p-4 text-sm dark:border-gray-600 dark:bg-gray-800"
    />
  )
}
