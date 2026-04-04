'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { X, Edit3, Loader2 } from 'lucide-react'
import { sanitizeHtml } from '@/lib/sanitize'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

interface SectionEditModalProps {
  docId: string
  sectionIndex: number
  sectionTitle: string
  currentContent: string
  isOpen: boolean
  onClose: () => void
  onRevised: (newContent: string) => void
}

/** 현재 콘텐츠를 안전하게 HTML 렌더링하는 컴포넌트 */
function CurrentContentPreview({ html }: { html: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !html) return
    ref.current.innerHTML = sanitizeHtml(html)
  }, [html])

  return (
    <div
      ref={ref}
      className="max-h-40 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
    />
  )
}

export function SectionEditModal({
  docId,
  sectionIndex,
  sectionTitle,
  currentContent,
  isOpen,
  onClose,
  onRevised,
}: SectionEditModalProps) {
  const [instruction, setInstruction] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 모달 열릴 때 텍스트영역에 포커스
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isOpen])

  /** 수정 요청 API 호출 */
  const handleSubmit = useCallback(async () => {
    if (!instruction.trim() || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/documents/${docId}/sections/${sectionIndex}/revise`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ instruction: instruction.trim() }),
        }
      )

      if (!res.ok) {
        throw new Error(`서버 오류 (${res.status})`)
      }

      const data = await res.json()
      onRevised(data.section || data.content)
    } catch (err) {
      const message = err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다'
      setError(`오류: ${message}`)
    } finally {
      setIsLoading(false)
    }
  }, [docId, sectionIndex, instruction, isLoading, onRevised])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 백드롭 */}
      <div
        data-testid="modal-backdrop"
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 모달 본체 */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${sectionTitle} 수정`}
        className="relative z-10 mx-4 w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Edit3 size={16} className="text-primary-500" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {sectionTitle} 수정
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
          >
            <X size={18} />
          </button>
        </div>

        {/* 본문 */}
        <div className="space-y-4 px-5 py-4">
          {/* 현재 내용 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
              현재 내용
            </label>
            <CurrentContentPreview html={currentContent} />
          </div>

          {/* 수정 요청 입력 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
              수정 요청
            </label>
            <textarea
              ref={textareaRef}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="수정 요청 사항을 입력해주세요..."
              disabled={isLoading}
              rows={3}
              className="w-full resize-none rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700 placeholder-gray-400 transition-colors focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
            />
          </div>

          {/* 에러 메시지 */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>

        {/* 푸터: 버튼 */}
        <div className="flex items-center justify-end gap-2 border-t border-gray-100 px-5 py-3 dark:border-gray-700">
          {isLoading && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <Loader2 size={14} className="animate-spin" />
              적용 중...
            </span>
          )}
          <button
            onClick={handleSubmit}
            disabled={!instruction.trim() || isLoading}
            className="rounded-lg bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-500 dark:hover:bg-primary-600"
          >
            적용
          </button>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="rounded-lg border border-gray-200 px-4 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
          >
            취소
          </button>
        </div>
      </div>
    </div>
  )
}
