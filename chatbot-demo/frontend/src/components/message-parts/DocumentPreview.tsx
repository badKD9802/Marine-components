'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { FileText, Download, Edit3 } from 'lucide-react'
import { sanitizeHtml } from '@/lib/sanitize'
import type { DocumentSection } from '@/types/message'
import { SectionEditModal } from './SectionEditModal'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

interface DocumentPreviewProps {
  docId: string
  title: string
  docType: string
  sections: DocumentSection[]
  files?: Record<string, string>
  reviewScore?: number
}

/** 섹션 HTML 콘텐츠를 안전하게 렌더링하는 내부 컴포넌트 */
function SectionContent({ html }: { html: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !html) return
    ref.current.innerHTML = sanitizeHtml(html)
  }, [html])

  if (!html || !html.trim()) return null

  return (
    <div
      ref={ref}
      className="prose prose-sm max-w-none dark:prose-invert overflow-x-auto text-sm text-gray-700 dark:text-gray-300"
    />
  )
}

export function DocumentPreview({
  docId,
  title,
  docType,
  sections: initialSections,
  files,
  reviewScore,
}: DocumentPreviewProps) {
  const [sections, setSections] = useState<DocumentSection[]>(initialSections)
  const [editingSection, setEditingSection] = useState<DocumentSection | null>(null)

  /** 다운로드 핸들러 */
  const handleDownload = useCallback(
    (format: string) => {
      const url = `${API_BASE_URL}/api/documents/${docId}/download?format=${format}`
      window.open(url, '_blank')
    },
    [docId]
  )

  /** 섹션 수정 완료 콜백 */
  const handleRevised = useCallback(
    (sectionIndex: number, newContent: string) => {
      setSections(prev =>
        prev.map(s =>
          s.section_index === sectionIndex
            ? { ...s, content: newContent, version: s.version + 1 }
            : s
        )
      )
    },
    []
  )

  return (
    <div className="my-2 rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800/80">
      {/* 헤더: 제목 + 점수 */}
      <div className="flex items-center gap-3 border-b border-gray-100 px-4 py-3 dark:border-gray-700">
        <FileText size={20} className="shrink-0 text-primary-500" />
        <h3 className="flex-1 text-base font-semibold text-gray-900 dark:text-gray-100">
          {title}
        </h3>
        {reviewScore != null && (
          <span className="rounded-full bg-green-50 px-2.5 py-0.5 text-sm font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
            {reviewScore}점
          </span>
        )}
      </div>

      {/* 다운로드 버튼 영역 */}
      {files && Object.keys(files).length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-gray-100 px-4 py-2.5 dark:border-gray-700">
          {Object.keys(files).map(format => (
            <button
              key={format}
              onClick={() => handleDownload(format)}
              aria-label={`${format.toUpperCase()} 다운로드`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            >
              <Download size={14} />
              {format.toUpperCase()} 다운로드
            </button>
          ))}
        </div>
      )}

      {/* 섹션 목록 */}
      <div className="space-y-0 divide-y divide-gray-100 dark:divide-gray-700">
        {sections.map(section => (
          <div
            key={section.section_index}
            className="group px-4 py-3 transition-colors hover:bg-gray-50/50 dark:hover:bg-gray-700/30"
          >
            {/* 섹션 헤더 */}
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                {section.section_title}
              </h4>
              <button
                onClick={() => setEditingSection(section)}
                aria-label={`${section.section_title} 수정`}
                className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-500 opacity-0 transition-all hover:border-primary-300 hover:text-primary-600 group-hover:opacity-100 dark:border-gray-600 dark:text-gray-400 dark:hover:border-primary-500 dark:hover:text-primary-400"
              >
                <Edit3 size={12} />
                수정
              </button>
            </div>

            {/* 섹션 콘텐츠 */}
            <SectionContent html={section.content} />
          </div>
        ))}
      </div>

      {/* 섹션 수정 모달 */}
      {editingSection && (
        <SectionEditModal
          docId={docId}
          sectionIndex={editingSection.section_index}
          sectionTitle={editingSection.section_title}
          currentContent={editingSection.content}
          isOpen={!!editingSection}
          onClose={() => setEditingSection(null)}
          onRevised={(newContent) => {
            handleRevised(editingSection.section_index, newContent)
            setEditingSection(null)
          }}
        />
      )}
    </div>
  )
}
