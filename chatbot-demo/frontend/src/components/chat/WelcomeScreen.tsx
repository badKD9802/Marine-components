'use client'

import { Bot, Calendar, Search, Mail, FileText } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'

const EXAMPLE_QUESTIONS = [
  { icon: Calendar, text: '이번 주 일정 알려줘', color: 'text-blue-500' },
  { icon: Search, text: '홍길동 직원 검색해줘', color: 'text-green-500' },
  { icon: Mail, text: '이메일 초안 작성해줘', color: 'text-orange-500' },
  { icon: FileText, text: '공공기관 문서 초안 작성하기', color: 'text-purple-500' },
]

export function WelcomeScreen() {
  const { sendMessage } = useSSEChat()

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
      </div>
    </div>
  )
}
