'use client'

import { useState } from 'react'
import { Bot, Calendar, Search, Mail, FileText, Shield, ChevronDown } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'

const EXAMPLE_QUESTIONS = [
  { icon: Calendar, text: '이번 주 일정 알려줘', color: 'text-blue-500', desc: '일정 조회·관리' },
  { icon: Search, text: '홍길동 직원 검색해줘', color: 'text-emerald-500', desc: '직원 정보 검색' },
  { icon: Mail, text: '이메일 초안 작성해줘', color: 'text-amber-500', desc: '메일 자동 작성' },
  { icon: FileText, text: '공공기관 문서 초안 작성하기', color: 'text-violet-500', desc: '문서 템플릿 생성' },
]

const SAFETY_REG_EXAMPLES = [
  '산업안전보건법 안전관리자 선임 기준',
  '중대재해처벌법 사업주 의무 알려줘',
  '위험성평가 절차와 방법',
  '산안법 제17조 내용',
]

export function WelcomeScreen() {
  const { sendMessage } = useSSEChat()
  const [safetyOpen, setSafetyOpen] = useState(false)

  return (
    <div className="flex flex-1 items-center justify-center px-4">
      <div className="w-full max-w-xl">
        {/* 헤더 */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-100 dark:bg-primary-900/50">
            <Bot size={28} className="text-primary-600" />
          </div>
          <h2 className="mb-1 text-2xl font-semibold text-gray-800 dark:text-gray-100">
            AI Assistant Demo
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            ReAct Agent 기반 AI 어시스턴트입니다. 아래 예시를 클릭하거나 직접 질문해보세요.
          </p>
        </div>

        {/* Bento Grid — 비대칭 퍼즐 배치 */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {/* 카드 0: 2칸 넓이 (큰 카드) */}
          <button
            onClick={() => sendMessage(EXAMPLE_QUESTIONS[0].text)}
            className="col-span-2 flex items-center gap-4 rounded-2xl border border-gray-200 bg-gradient-to-br from-blue-50 to-white px-5 py-5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:border-gray-700 dark:from-blue-950/30 dark:to-gray-800/80"
          >
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/50">
              <Calendar size={24} className="text-blue-500" />
            </span>
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{EXAMPLE_QUESTIONS[0].text}</p>
              <p className="mt-0.5 text-xs text-gray-400">{EXAMPLE_QUESTIONS[0].desc}</p>
            </div>
          </button>

          {/* 카드 1: 1칸 (작은 카드) */}
          <button
            onClick={() => sendMessage(EXAMPLE_QUESTIONS[1].text)}
            className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-gradient-to-br from-emerald-50 to-white px-3 py-5 text-center transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:border-gray-700 dark:from-emerald-950/30 dark:to-gray-800/80"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 dark:bg-emerald-900/50">
              <Search size={20} className="text-emerald-500" />
            </span>
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{EXAMPLE_QUESTIONS[1].desc}</p>
            </div>
          </button>

          {/* 카드 2: 1칸 */}
          <button
            onClick={() => sendMessage(EXAMPLE_QUESTIONS[2].text)}
            className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-gradient-to-br from-amber-50 to-white px-3 py-5 text-center transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:border-gray-700 dark:from-amber-950/30 dark:to-gray-800/80"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-900/50">
              <Mail size={20} className="text-amber-500" />
            </span>
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{EXAMPLE_QUESTIONS[2].desc}</p>
            </div>
          </button>

          {/* 카드 3: 2칸 넓이 */}
          <button
            onClick={() => sendMessage(EXAMPLE_QUESTIONS[3].text)}
            className="col-span-2 flex items-center gap-4 rounded-2xl border border-gray-200 bg-gradient-to-br from-violet-50 to-white px-5 py-5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:border-gray-700 dark:from-violet-950/30 dark:to-gray-800/80"
          >
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-violet-100 dark:bg-violet-900/50">
              <FileText size={24} className="text-violet-500" />
            </span>
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{EXAMPLE_QUESTIONS[3].text}</p>
              <p className="mt-0.5 text-xs text-gray-400">{EXAMPLE_QUESTIONS[3].desc}</p>
            </div>
          </button>
        </div>

        {/* 안전 법령 검색 — 벤토 스타일 */}
        <div className="mt-3 rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white dark:border-blue-800 dark:from-blue-950/30 dark:to-gray-800/80">
          <button
            onClick={() => setSafetyOpen(!safetyOpen)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/50">
                <Shield size={18} className="text-blue-500" />
              </span>
              <div>
                <span className="text-sm font-semibold text-blue-700 dark:text-blue-300">
                  안전 법령 검색
                </span>
                <span className="ml-2 text-xs text-blue-500 dark:text-blue-400">
                  이렇게 질문하세요
                </span>
              </div>
            </div>
            <ChevronDown
              size={18}
              className={`text-blue-400 transition-transform duration-200 ${safetyOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {safetyOpen && (
            <div className="space-y-2 px-4 pb-4">
              {SAFETY_REG_EXAMPLES.slice(0, 3).map((text) => (
                <button
                  key={text}
                  onClick={() => sendMessage(text)}
                  className="flex w-full items-center gap-2 rounded-xl border border-blue-100 bg-white/80 px-3 py-2 text-left text-sm text-gray-700 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm dark:border-blue-800 dark:bg-gray-800/60 dark:text-gray-300"
                >
                  <span className="text-blue-400">{'>'}</span>
                  {text}
                </button>
              ))}
              <p className="pl-1 text-xs text-blue-400 dark:text-blue-500">
                ... 법령명, 조문번호 등으로 자유롭게 질문하세요
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
