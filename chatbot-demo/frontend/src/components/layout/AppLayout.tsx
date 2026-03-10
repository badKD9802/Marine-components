'use client'

import { Sidebar } from './Sidebar'
import { ChatHeader } from './ChatHeader'
import { useUIStore } from '@/stores/uiStore'

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen } = useUIStore()

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <div
        className={`flex flex-1 flex-col transition-all duration-300 ${
          sidebarOpen ? 'md:ml-[280px]' : ''
        }`}
      >
        <ChatHeader />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
