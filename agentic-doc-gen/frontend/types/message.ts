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

/** 양식 후보 (문서 생성 플로우에서 백엔드가 반환) */
export interface TemplateCandidate {
  id: string
  title: string
  category: string
  score?: number
}

/** 예시 문서 (양식 선택 후 백엔드가 반환) */
export interface ExampleDoc {
  id: string
  title: string
  is_mine: boolean
  preview?: string  // 내용 미리보기 (첫 100자)
}

/** 문서 미리보기 섹션 */
export interface DocumentSection {
  section_index: number
  section_title: string
  content: string  // HTML 렌더링용
  version: number
}

/** 문서 미리보기 데이터 */
export interface DocumentPreviewData {
  docId: string
  title: string
  docType: string
  sections: DocumentSection[]
  files?: Record<string, string>  // {"hwpx": "/path", "pptx": "/path"}
  reviewScore?: number
}

export interface MessagePart {
  type: 'text' | 'html' | 'progress' | 'buttons' | 'template_selector' | 'example_selector' | 'document_preview'
  content?: string
  steps?: ProgressStep[]
  buttons?: QuickButton[]
  templateCandidates?: TemplateCandidate[]
  examples?: ExampleDoc[]
  templateTitle?: string
  documentPreview?: DocumentPreviewData
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
