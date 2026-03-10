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
                {step.result_count !== undefined && (
                  <span className="ml-1 text-gray-400">({step.result_count}건)</span>
                )}
              </p>
              {step.preview && (
                <p className="mt-0.5 text-xs text-gray-400 line-clamp-2">{step.preview}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
