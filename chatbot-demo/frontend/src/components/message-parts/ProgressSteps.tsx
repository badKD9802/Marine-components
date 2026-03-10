'use client'

import { useState, useEffect } from 'react'
import type { ProgressStep } from '@/types/message'

export function ProgressSteps({ steps, isStreaming }: { steps: ProgressStep[]; isStreaming?: boolean }) {
  const [isOpen, setIsOpen] = useState(true)

  const hasActive = steps.some(s => s.status === 'active' || s.status === 'running')
  const completedCount = steps.filter(s => s.status === 'completed' || s.status === 'done').length

  // 모든 단계가 완료되면 자동으로 접기
  useEffect(() => {
    if (!hasActive && completedCount > 0 && !isStreaming) {
      setIsOpen(false)
    }
  }, [hasActive, completedCount, isStreaming])

  if (!steps.length) return null

  return (
    <div className="my-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
      >
        {hasActive ? (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        ) : (
          <span className="text-green-500 text-base">&#10003;</span>
        )}
        <span className="font-medium">
          {hasActive
            ? `작업 수행 중... (${completedCount}/${steps.length})`
            : `${completedCount}개 작업 완료`}
        </span>
        <svg
          className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="ml-6 mt-2 space-y-1.5 border-l-2 border-gray-200 pl-4 dark:border-gray-600">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <StepIcon status={step.status} />
              <div className="flex-1 min-w-0">
                <span className="text-gray-700 dark:text-gray-300">{step.title}</span>
                {step.result_count != null && (
                  <span className="ml-1.5 text-gray-400 text-xs">
                    ({typeof step.result_count === 'number' ? `${step.result_count}건` : step.result_count})
                  </span>
                )}
                <PreviewContent preview={step.preview} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StepIcon({ status }: { status: string }) {
  if (status === 'active' || status === 'running') {
    return (
      <span className="mt-0.5 inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent shrink-0" />
    )
  }
  if (status === 'completed' || status === 'done') {
    return <span className="text-green-500 shrink-0 mt-0.5">&#10003;</span>
  }
  if (status === 'error') {
    return <span className="text-red-500 shrink-0 mt-0.5">&#10007;</span>
  }
  return <span className="text-gray-300 shrink-0 mt-0.5">&#9675;</span>
}

function PreviewContent({ preview }: { preview?: ProgressStep['preview'] }) {
  if (!preview) return null

  // 문자열인 경우
  if (typeof preview === 'string') {
    return <p className="mt-0.5 text-xs text-gray-400 line-clamp-2">{preview}</p>
  }

  // 객체 배열인 경우 [{icon, text, sub}]
  if (Array.isArray(preview)) {
    return (
      <div className="mt-0.5 space-y-0.5">
        {preview.slice(0, 3).map((item, i) => (
          <p key={i} className="text-xs text-gray-400">
            {item.icon && <span className="mr-1">{item.icon}</span>}
            <span>{item.text}</span>
            {item.sub && <span className="ml-1 text-gray-300">&middot; {item.sub}</span>}
          </p>
        ))}
        {preview.length > 3 && (
          <p className="text-xs text-gray-300">외 {preview.length - 3}건...</p>
        )}
      </div>
    )
  }

  return null
}
