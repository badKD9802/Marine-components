import type { Message } from '@/types/message'

export function UserMessage({ message }: { message: Message }) {
  const text = message.parts.find(p => p.type === 'text')?.content || ''

  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-gray-100 px-4 py-3 text-sm text-gray-800 dark:bg-gray-700 dark:text-gray-100">
        <p className="whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}
