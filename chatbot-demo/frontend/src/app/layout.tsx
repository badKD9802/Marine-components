import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI Assistant Demo',
  description: 'ReAct Agent 기반 AI 챗봇 데모',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className="antialiased">{children}</body>
    </html>
  )
}
