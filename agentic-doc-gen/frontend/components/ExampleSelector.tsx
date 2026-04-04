'use client'

import { useState } from 'react'
import { BookOpen, Lock, FileText, Upload, ChevronDown, ChevronUp } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import type { ExampleDoc } from '@/types/message'

interface ExampleSelectorProps {
  templateTitle: string
  examples: ExampleDoc[]
}

/**
 * 예시 선택 UI — 양식 선택 후 백엔드가 예시 목록을 반환하면 표시
 * 체크박스로 개별 선택하거나, "전체 사용" / "선택 완료" 버튼으로 전송한다.
 */
export function ExampleSelector({ templateTitle, examples }: ExampleSelectorProps) {
  const { sendMessage, isStreaming } = useSSEChat()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expandedPreviews, setExpandedPreviews] = useState<Set<string>>(new Set())

  if (!examples.length) return null

  // 내 예시 / 기본 제공 예시 분리
  const myExamples = examples.filter((e) => e.is_mine)
  const defaultExamples = examples.filter((e) => !e.is_mine)

  /** 체크박스 토글 */
  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  /** 미리보기 토글 */
  const togglePreview = (id: string) => {
    setExpandedPreviews((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  /** "선택 완료" — 선택된 예시 ID 전송 */
  const handleConfirm = () => {
    if (isStreaming || selected.size === 0) return
    const ids = Array.from(selected)
    sendMessage(`example_ids:[${ids.join(',')}] 사용`)
  }

  /** "전체 사용" — 모든 예시 사용 */
  const handleUseAll = () => {
    if (isStreaming) return
    sendMessage('전체 예시 사용')
  }

  /** "내 파일 업로드" — placeholder (향후 구현) */
  const handleUpload = () => {
    // TODO: 파일 업로드 기능 구현
    alert('파일 업로드 기능은 준비 중입니다.')
  }

  /** 예시 항목 렌더링 */
  const renderExampleItem = (example: ExampleDoc) => {
    const isExpanded = expandedPreviews.has(example.id)
    const isChecked = selected.has(example.id)

    return (
      <div key={example.id} className="rounded-xl border border-gray-100 bg-gray-50 dark:border-gray-600 dark:bg-gray-700/60">
        <div className="flex items-center gap-2 px-3 py-2.5">
          {/* 체크박스 */}
          <input
            type="checkbox"
            checked={isChecked}
            onChange={() => toggleSelect(example.id)}
            className="h-4 w-4 shrink-0 rounded border-gray-300 text-primary-500 accent-primary-500 focus:ring-primary-400 dark:border-gray-500"
          />
          {/* 제목 */}
          <span className="flex-1 text-sm text-gray-800 dark:text-gray-200">
            {example.title}
          </span>
          {/* 미리보기 버튼 */}
          {example.preview && (
            <button
              onClick={() => togglePreview(example.id)}
              className="flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-600"
            >
              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              미리보기
            </button>
          )}
        </div>
        {/* 미리보기 내용 */}
        {isExpanded && example.preview && (
          <div className="border-t border-gray-100 px-3 py-2 dark:border-gray-600">
            <p className="text-xs leading-relaxed text-gray-500 dark:text-gray-400">
              {example.preview}
            </p>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="w-full max-w-md animate-fade-in-up rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800/90">
      {/* 헤더 */}
      <div className="mb-1 flex items-center gap-2">
        <BookOpen size={18} className="text-primary-500" />
        <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">
          참고할 예시를 선택해주세요
        </span>
      </div>
      {templateTitle && (
        <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
          양식: {templateTitle} &middot; 선택 안 하면 전체 참고
        </p>
      )}

      {/* 내 예시 섹션 */}
      {myExamples.length > 0 && (
        <div className="mb-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <Lock size={13} className="text-amber-500" />
            <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">내 예시</span>
          </div>
          <div className="space-y-1.5">
            {myExamples.map(renderExampleItem)}
          </div>
        </div>
      )}

      {/* 기본 제공 예시 섹션 */}
      {defaultExamples.length > 0 && (
        <div className="mb-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <FileText size={13} className="text-primary-500" />
            <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">기본 제공 예시</span>
          </div>
          <div className="space-y-1.5">
            {defaultExamples.map(renderExampleItem)}
          </div>
        </div>
      )}

      {/* 하단 액션 버튼 */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={handleUpload}
          disabled={isStreaming}
          className="flex items-center gap-1 rounded-full border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
        >
          <Upload size={14} />
          내 파일 업로드
        </button>
        <button
          onClick={handleConfirm}
          disabled={isStreaming || selected.size === 0}
          className="rounded-full bg-primary-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-primary-600 disabled:opacity-50 dark:bg-primary-600 dark:hover:bg-primary-500"
        >
          선택 완료 ({selected.size})
        </button>
        <button
          onClick={handleUseAll}
          disabled={isStreaming}
          className="rounded-full border border-primary-300 px-3 py-1.5 text-xs font-medium text-primary-600 transition-colors hover:bg-primary-50 disabled:opacity-50 dark:border-primary-600 dark:text-primary-400 dark:hover:bg-primary-900/20"
        >
          전체 사용
        </button>
      </div>
    </div>
  )
}
