'use client'

import { LoadingStep } from '@/lib/types'

type LoadingStepsProps = {
  currentStep: LoadingStep | null
}

const STEPS: { key: LoadingStep; label: string }[] = [
  { key: 'analyzing', label: 'Analyzing your question' },
  { key: 'searching', label: 'Searching 300+ episodes' },
  { key: 'finding', label: 'Finding relevant quotes' },
  { key: 'synthesizing', label: 'Synthesizing response' },
]

export function LoadingSteps({ currentStep }: LoadingStepsProps) {
  const currentIndex = currentStep ? STEPS.findIndex((s) => s.key === currentStep) : -1

  return (
    <div className="py-6 px-4 message-enter">
      <div className="max-w-2xl mx-auto">
        <div className="bg-[var(--color-surface)] rounded-2xl p-6 border border-[var(--color-border)]">
          <div className="space-y-1">
            {STEPS.map((step, index) => {
              const isComplete = index < currentIndex
              const isActive = index === currentIndex
              const isPending = index > currentIndex

              return (
                <div key={step.key} className="loading-step">
                  <div
                    className={`loading-step-indicator ${
                      isComplete ? 'complete' : isActive ? 'active' : 'pending'
                    }`}
                  >
                    {isComplete && (
                      <svg
                        className="w-3 h-3"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={3}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    )}
                  </div>
                  <span
                    className={`loading-step-text ${
                      isComplete ? 'complete' : isActive ? 'active' : ''
                    }`}
                  >
                    {step.label}
                    {isActive && <span className="loading-dots ml-1" />}
                  </span>
                </div>
              )
            })}
          </div>

          <div className="mt-4 pt-4 border-t border-[var(--color-border-subtle)]">
            <p className="text-xs text-[var(--color-text-muted)]">
              Deep research typically takes 30-60 seconds
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
