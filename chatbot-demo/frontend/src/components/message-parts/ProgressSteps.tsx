import type { ProgressStep } from '@/types/message'

export function ProgressSteps({ steps }: { steps: ProgressStep[] }) {
  if (!steps.length) return null

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm dark:border-gray-600 dark:bg-gray-800">
      <div className="space-y-2">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="mt-0.5 shrink-0">
              {step.status === 'running' && (
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
              )}
              {step.status === 'done' && <span className="text-green-500">&#10003;</span>}
              {step.status === 'error' && <span className="text-red-500">&#10007;</span>}
            </span>
            <div className="flex-1">
              <p className="font-medium text-gray-700 dark:text-gray-300">
                {step.title}
                {step.result_count != null && (
                  <span className="ml-1 text-gray-400">
                    ({typeof step.result_count === 'number' ? `${step.result_count}건` : step.result_count})
                  </span>
                )}
              </p>
              <PreviewContent preview={step.preview} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
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
      <div className="mt-1 space-y-0.5">
        {preview.slice(0, 3).map((item, i) => (
          <p key={i} className="text-xs text-gray-400">
            {item.icon && <span className="mr-1">{item.icon}</span>}
            <span>{item.text}</span>
            {item.sub && <span className="ml-1 text-gray-300">({item.sub})</span>}
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
