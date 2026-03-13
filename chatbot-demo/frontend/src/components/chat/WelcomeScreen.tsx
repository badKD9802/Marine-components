'use client'

import { useState } from 'react'
import { Bot, Calendar, Search, Mail, FileText, Shield, ChevronDown } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'

const EXAMPLE_QUESTIONS = [
  { icon: Calendar, text: '이번 주 일정 알려줘', color: 'text-blue-500' },
  { icon: Search, text: '홍길동 직원 검색해줘', color: 'text-green-500' },
  { icon: Mail, text: '이메일 초안 작성해줘', color: 'text-orange-500' },
  { icon: FileText, text: '공공기관 문서 초안 작성하기', color: 'text-purple-500' },
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
      <div className="max-w-lg text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-100 dark:bg-primary-900/50">
          <Bot size={32} className="text-primary-600" />
        </div>
        <h2 className="mb-2 text-2xl font-semibold text-gray-800 dark:text-gray-100">
          AI Assistant Demo
        </h2>
        <p className="mb-8 text-gray-500 dark:text-gray-400">
          ReAct Agent 기반 AI 어시스턴트입니다. 아래 예시를 클릭하거나 직접 질문해보세요.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {EXAMPLE_QUESTIONS.map(({ icon: Icon, text, color }) => (
            <button
              key={text}
              onClick={() => sendMessage(text)}
              className="flex items-center gap-3 rounded-xl border border-gray-200 px-4 py-3 text-left text-sm text-gray-700 transition-all hover:border-primary-300 hover:bg-primary-50 dark:border-gray-600 dark:text-gray-300 dark:hover:border-primary-600 dark:hover:bg-primary-900/20"
            >
              <Icon size={20} className={color} />
              {text}
            </button>
          ))}
        </div>

        {/* 안전 법령 검색 가이드 카드 */}
        <div className="mt-4 rounded-xl border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-900/20">
          <button
            onClick={() => setSafetyOpen(!safetyOpen)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <div className="flex items-center gap-3">
              <Shield size={20} className="text-blue-500" />
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
              {SAFETY_REG_EXAMPLES.map((text) => (
                <button
                  key={text}
                  onClick={() => sendMessage(text)}
                  className="flex w-full items-center gap-2 rounded-lg border border-blue-200 bg-white px-3 py-2 text-left text-sm text-gray-700 transition-all hover:border-blue-400 hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-900/30 dark:text-gray-300 dark:hover:bg-blue-800/40"
                >
                  <span className="text-blue-400">{'>'}</span>
                  {text}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
