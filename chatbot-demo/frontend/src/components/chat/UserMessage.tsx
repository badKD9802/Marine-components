import type { Message } from '@/types/message'

export function UserMessage({ message }: { message: Message }) {
  const text = message.parts.find(p => p.type === 'text')?.content || ''

  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary-600 px-4 py-3 text-sm text-white shadow-sm">
        <p className="whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}
