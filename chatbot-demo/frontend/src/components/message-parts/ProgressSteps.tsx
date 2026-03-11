'use client'

import { useState, useEffect, useRef } from 'react'
import { CheckCircle2, XCircle, Circle, Loader2, ChevronDown } from 'lucide-react'
import type { ProgressStep } from '@/types/message'

export function ProgressSteps({ steps, isStreaming }: { steps: ProgressStep[]; isStreaming?: boolean }) {
  const [isOpen, setIsOpen] = useState(true)
  const [elapsed, setElapsed] = useState(0)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const hasActive = steps.some(s => s.status === 'active' || s.status === 'running')
  const completedCount = steps.filter(s => s.status === 'completed' || s.status === 'done').length

  // 모든 단계가 완료되면 자동으로 접기
  useEffect(() => {
    if (!hasActive && completedCount > 0 && !isStreaming) {
      setIsOpen(false)
    }
  }, [hasActive, completedCount, isStreaming])

  // 경과 시간 타이머
  useEffect(() => {
    if (hasActive) {
      setElapsed(0)
      intervalRef.current = setInterval(() => setElapsed(prev => prev + 1), 1000)
    } else {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [hasActive])

  if (!steps.length) return null

  return (
    <div className="my-2 rounded-lg border border-gray-200 bg-gray-50/50 dark:border-gray-700 dark:bg-gray-800/50">
      {/* 헤더 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-label={hasActive ? '진행 중인 작업 목록' : '완료된 작업 목록'}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm transition-colors
                   text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
      >
        {hasActive ? (
          <Loader2 size={16} className="animate-spin text-primary-500" />
        ) : (
          <CheckCircle2 size={16} className="text-green-500" />
        )}
        <span className={`flex-1 text-left font-medium ${hasActive ? 'shimmer-text' : ''}`}>
          {hasActive
            ? `작업 수행 중... (${completedCount}/${steps.length})`
            : `${completedCount}개 작업 완료`}
        </span>
        {hasActive && elapsed > 0 && (
          <span className="text-xs text-gray-400 tabular-nums">{elapsed}s</span>
        )}
        <ChevronDown size={16} className={`transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Steps — CSS Grid 접힘/펼침 */}
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-in-out"
        style={{ gridTemplateRows: isOpen ? '1fr' : '0fr' }}
      >
        <div className="overflow-hidden">
          <div className="space-y-1 px-3 pb-3 pt-0.5" role="list">
            {steps.map((step, i) => (
              <div key={step.title} role="listitem"
                   className="flex items-start gap-2.5 text-sm animate-fade-in-up"
                   style={{ animationDelay: `${i * 50}ms` }}>
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
        </div>
      </div>
    </div>
  )
}

function StepIcon({ status }: { status: string }) {
  const base = "mt-0.5 shrink-0"
  if (status === 'active' || status === 'running')
    return <Loader2 size={14} className={`${base} animate-spin text-primary-500`} />
  if (status === 'completed' || status === 'done')
    return <CheckCircle2 size={14} className={`${base} text-green-500`} />
  if (status === 'error')
    return <XCircle size={14} className={`${base} text-red-500`} />
  return <Circle size={14} className={`${base} text-gray-300 dark:text-gray-600`} />
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
