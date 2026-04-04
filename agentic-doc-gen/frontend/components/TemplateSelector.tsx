'use client'

import { useState } from 'react'
import { FileText, Search, ChevronDown } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import type { TemplateCandidate } from '@/types/message'

/** 초기 표시 개수 */
const INITIAL_SHOW_COUNT = 5

interface TemplateSelectorProps {
  candidates: TemplateCandidate[]
}

/**
 * 양식 선택 UI — 백엔드에서 need_template_selection 응답 시 표시
 * 사용자가 양식을 클릭하면 sendMessage로 선택 결과를 전송한다.
 */
export function TemplateSelector({ candidates }: TemplateSelectorProps) {
  const { sendMessage, isStreaming } = useSSEChat()
  const [showAll, setShowAll] = useState(false)
  const [searchMode, setSearchMode] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  if (!candidates.length) return null

  const visibleCandidates = showAll ? candidates : candidates.slice(0, INITIAL_SHOW_COUNT)
  const hasMore = candidates.length > INITIAL_SHOW_COUNT

  /** 양식 선택 → 메시지 전송 */
  const handleSelect = (candidate: TemplateCandidate) => {
    if (isStreaming) return
    sendMessage(`template_id:${candidate.id}로 작성해줘`)
  }

  /** "더 보기" → 백엔드에 추가 양식 요청 */
  const handleShowMore = () => {
    if (showAll) {
      // 이미 전부 표시 중이면 백엔드에 추가 요청
      if (!isStreaming) sendMessage('다른 양식도 보여줘')
    } else {
      setShowAll(true)
    }
  }

  /** 직접 검색 → 입력 후 메시지 전송 */
  const handleSearchSubmit = () => {
    const q = searchQuery.trim()
    if (!q || isStreaming) return
    sendMessage(q)
    setSearchQuery('')
    setSearchMode(false)
  }

  return (
    <div className="w-full max-w-md animate-fade-in-up rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800/90">
      {/* 헤더 */}
      <div className="mb-3 flex items-center gap-2">
        <FileText size={18} className="text-primary-500" />
        <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">
          어떤 양식으로 작성할까요?
        </span>
      </div>

      {/* 양식 목록 */}
      <div className="space-y-2">
        {visibleCandidates.map((c) => (
          <button
            key={c.id}
            onClick={() => handleSelect(c)}
            disabled={isStreaming}
            className="flex w-full items-center justify-between rounded-xl border border-gray-100 bg-gray-50 px-3 py-2.5 text-left transition-all duration-150 hover:-translate-y-0.5 hover:border-primary-200 hover:bg-primary-50 hover:shadow-sm disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700/60 dark:hover:border-primary-600 dark:hover:bg-primary-900/20"
          >
            <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
              {c.title}
            </span>
            <span className="ml-2 shrink-0 rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-600 dark:text-gray-400">
              {c.category}
            </span>
          </button>
        ))}
      </div>

      {/* 직접 검색 입력 */}
      {searchMode && (
        <div className="mt-3 flex items-center gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearchSubmit()}
            placeholder="양식 이름을 입력하세요..."
            className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder-gray-500 dark:focus:border-primary-500"
            autoFocus
          />
          <button
            onClick={handleSearchSubmit}
            disabled={isStreaming || !searchQuery.trim()}
            className="rounded-lg bg-primary-500 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-600 disabled:opacity-50 dark:bg-primary-600 dark:hover:bg-primary-500"
          >
            검색
          </button>
        </div>
      )}

      {/* 하단 액션 버튼 */}
      <div className="mt-3 flex flex-wrap gap-2">
        {hasMore && (
          <button
            onClick={handleShowMore}
            disabled={isStreaming}
            className="flex items-center gap-1 rounded-full border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
          >
            <ChevronDown size={14} />
            더 보기
          </button>
        )}
        <button
          onClick={() => setSearchMode(!searchMode)}
          disabled={isStreaming}
          className="flex items-center gap-1 rounded-full border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
        >
          <Search size={14} />
          직접 검색
        </button>
      </div>
    </div>
  )
}
