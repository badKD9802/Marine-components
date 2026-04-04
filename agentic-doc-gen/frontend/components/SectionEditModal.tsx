'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { X, Edit3, Loader2, Wand2, PenLine } from 'lucide-react'
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

/** 현재 콘텐츠를 안전하게 HTML 렌더링하는 컴포넌트 (읽기 전용) */
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

/** contentEditable 기반 WYSIWYG 편집기 */
function WysiwygEditor({
  initialHtml,
  onChange,
  disabled,
}: {
  initialHtml: string
  onChange: (html: string) => void
  disabled?: boolean
}) {
  const editorRef = useRef<HTMLDivElement>(null)

  // 초기 HTML 설정
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = sanitizeHtml(initialHtml)
    }
  }, [initialHtml])

  const handleInput = useCallback(() => {
    if (editorRef.current) {
      onChange(editorRef.current.innerHTML)
    }
  }, [onChange])

  /** 서식 명령 실행 */
  const exec = useCallback((command: string, value?: string) => {
    document.execCommand(command, false, value)
    editorRef.current?.focus()
    handleInput()
  }, [handleInput])

  return (
    <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-600 dark:bg-gray-900">
      {/* 툴바 */}
      <div className="flex flex-wrap items-center gap-0.5 border-b border-gray-200 px-2 py-1.5 dark:border-gray-600">
        {/* 텍스트 서식 */}
        <ToolbarButton onClick={() => exec('bold')} title="굵게 (Ctrl+B)" label="B" className="font-bold" />
        <ToolbarButton onClick={() => exec('italic')} title="기울임 (Ctrl+I)" label="I" className="italic" />
        <ToolbarButton onClick={() => exec('underline')} title="밑줄 (Ctrl+U)" label="U" className="underline" />
        <ToolbarButton onClick={() => exec('strikeThrough')} title="취소선" label="S" className="line-through" />
        <ToolbarDivider />
        {/* 제목 — 드롭다운 */}
        <ToolbarDropdown
          label="제목"
          items={[
            { label: '큰 제목 (H2)', onClick: () => exec('formatBlock', 'h2') },
            { label: '중간 제목 (H3)', onClick: () => exec('formatBlock', 'h3') },
            { label: '작은 제목 (H4)', onClick: () => exec('formatBlock', 'h4') },
            { label: '본문 (P)', onClick: () => exec('formatBlock', 'p') },
          ]}
        />
        <ToolbarDivider />
        {/* 글머리 기호 — 드롭다운 */}
        <ToolbarDropdown
          label="목록"
          items={[
            { label: '● 글머리 기호', onClick: () => exec('insertUnorderedList') },
            { label: '1. 번호 목록', onClick: () => exec('insertOrderedList') },
          ]}
        />
        <ToolbarDivider />
        {/* 정렬 */}
        <ToolbarButton onClick={() => exec('justifyLeft')} title="왼쪽 정렬" label="☰" />
        <ToolbarButton onClick={() => exec('justifyCenter')} title="가운데 정렬" label="≡" />
        <ToolbarButton onClick={() => exec('justifyRight')} title="오른쪽 정렬" label="☷" />
        <ToolbarDivider />
        {/* 들여쓰기 */}
        <ToolbarButton onClick={() => exec('indent')} title="들여쓰기" label="→|" className="text-[10px]" />
        <ToolbarButton onClick={() => exec('outdent')} title="내어쓰기" label="|←" className="text-[10px]" />
        <ToolbarDivider />
        {/* 기타 */}
        <ToolbarButton onClick={() => exec('insertHorizontalRule')} title="구분선" label="—" />
        <ToolbarButton onClick={() => exec('removeFormat')} title="서식 제거" label="✕" className="text-red-500" />
      </div>

      {/* 편집 영역 */}
      <div
        ref={editorRef}
        contentEditable={!disabled}
        onInput={handleInput}
        suppressContentEditableWarning
        className="prose prose-sm max-w-none dark:prose-invert min-h-[200px] max-h-[400px] overflow-y-auto p-3 text-sm text-gray-700 focus:outline-none dark:text-gray-300 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-gray-300 [&_td]:p-2 [&_th]:border [&_th]:border-gray-300 [&_th]:bg-gray-100 [&_th]:p-2 dark:[&_td]:border-gray-600 dark:[&_th]:border-gray-600 dark:[&_th]:bg-gray-700"
      />
    </div>
  )
}

/** 툴바 버튼 */
function ToolbarButton({
  onClick,
  title,
  label,
  className: extraClass,
}: {
  onClick: () => void
  title: string
  label: string
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="flex h-7 min-w-[28px] items-center justify-center rounded px-1 text-xs text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
    >
      <span className={extraClass}>{label}</span>
    </button>
  )
}

/** 툴바 드롭다운 (제목, 목록 등) */
function ToolbarDropdown({
  label,
  items,
}: {
  label: string
  items: Array<{ label: string; onClick: () => void }>
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // 외부 클릭 시 닫기
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        className={`flex h-7 items-center gap-0.5 rounded px-1.5 text-xs transition-colors ${
          open
            ? 'bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100'
            : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700'
        }`}
      >
        {label}
        <svg className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 min-w-[140px] rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-600 dark:bg-gray-800">
          {items.map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => { item.onClick(); setOpen(false) }}
              className="block w-full px-3 py-1.5 text-left text-xs text-gray-700 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/** 툴바 구분선 */
function ToolbarDivider() {
  return <div className="mx-0.5 h-5 w-px bg-gray-200 dark:bg-gray-600" />
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
  const [mode, setMode] = useState<'ai' | 'manual'>('ai')
  const [instruction, setInstruction] = useState('')
  const [manualHtml, setManualHtml] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 모달 열릴 때 초기화
  useEffect(() => {
    if (isOpen) {
      setMode('ai')
      setInstruction('')
      setManualHtml(currentContent)
      setError(null)
      setTimeout(() => textareaRef.current?.focus(), 100)
    }
  }, [isOpen, currentContent])

  /** AI 수정 요청 API 호출 */
  const handleAiSubmit = useCallback(async () => {
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

  /** 직접 수정 적용 */
  const handleManualSubmit = useCallback(() => {
    if (!manualHtml.trim()) return
    onRevised(manualHtml)
  }, [manualHtml, onRevised])

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
        className="relative z-10 mx-4 w-full max-w-2xl rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
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

        {/* 모드 탭 */}
        <div className="flex border-b border-gray-100 px-5 dark:border-gray-700">
          <button
            onClick={() => setMode('ai')}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors ${
              mode === 'ai'
                ? 'border-b-2 border-primary-500 text-primary-600 dark:text-primary-400'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400'
            }`}
          >
            <Wand2 size={14} />
            AI 수정
          </button>
          <button
            onClick={() => setMode('manual')}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors ${
              mode === 'manual'
                ? 'border-b-2 border-primary-500 text-primary-600 dark:text-primary-400'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400'
            }`}
          >
            <PenLine size={14} />
            직접 수정
          </button>
        </div>

        {/* 본문 */}
        <div className="space-y-4 px-5 py-4">
          {mode === 'ai' ? (
            <>
              {/* 현재 내용 미리보기 */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
                  현재 내용
                </label>
                <CurrentContentPreview html={currentContent} />
              </div>

              {/* AI 수정 요청 */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
                  수정 요청
                </label>
                <p className="mb-2 text-xs text-gray-400 dark:text-gray-500">
                  원하는 수정 사항을 자연어로 입력하면 AI가 내용을 수정합니다.
                </p>
                <textarea
                  ref={textareaRef}
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  placeholder="예: 표로 바꿔주고 수치를 강조해줘, 문체를 딱딱하게 바꿔줘..."
                  disabled={isLoading}
                  rows={3}
                  className="w-full resize-none rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700 placeholder-gray-400 transition-colors focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
                />
              </div>
            </>
          ) : (
            /* 직접 수정 — WYSIWYG 편집기 */
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
                내용 직접 편집
              </label>
              <p className="mb-2 text-xs text-gray-400 dark:text-gray-500">
                문서를 보이는 그대로 편집할 수 있습니다. 상단 툴바로 서식을 적용하세요.
              </p>
              <WysiwygEditor
                initialHtml={currentContent}
                onChange={setManualHtml}
                disabled={isLoading}
              />
            </div>
          )}

          {/* 에러 메시지 */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-end gap-2 border-t border-gray-100 px-5 py-3 dark:border-gray-700">
          {isLoading && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <Loader2 size={14} className="animate-spin" />
              AI가 수정 중...
            </span>
          )}
          {mode === 'ai' ? (
            <button
              onClick={handleAiSubmit}
              disabled={!instruction.trim() || isLoading}
              className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-500 dark:hover:bg-primary-600"
            >
              <Wand2 size={14} />
              AI 수정 적용
            </button>
          ) : (
            <button
              onClick={handleManualSubmit}
              disabled={!manualHtml.trim() || isLoading}
              className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-500 dark:hover:bg-primary-600"
            >
              <PenLine size={14} />
              수정 적용
            </button>
          )}
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
