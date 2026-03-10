export interface ProgressStep {
  title: string
  status: 'running' | 'done' | 'error' | 'active' | 'completed'
  result_count?: number | string
  preview?: string | Array<{ icon?: string; text?: string; sub?: string }>
}

export interface QuickButton {
  title: string
  value: string
}

export interface MessagePart {
  type: 'text' | 'html' | 'progress' | 'buttons'
  content?: string
  steps?: ProgressStep[]
  buttons?: QuickButton[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  parts: MessagePart[]
  timestamp: number
  isStreaming?: boolean
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: number
  updatedAt: number
}
