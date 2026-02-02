'use client'

import { useEffect, useRef } from 'react'
import { Message, LoadingStep } from '@/lib/types'
import { MessageBubble } from './MessageBubble'
import { LoadingSteps } from './LoadingSteps'
import { WelcomeScreen } from './WelcomeScreen'

type ChatContainerProps = {
  messages: Message[]
  isLoading: boolean
  loadingStep: LoadingStep | null
  onCitationClick: (citationId: string) => void
  onSuggestionClick: (suggestion: string) => void
}

export function ChatContainer({
  messages,
  isLoading,
  loadingStep,
  onCitationClick,
  onSuggestionClick,
}: ChatContainerProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isLoading])

  const isEmpty = messages.length === 0 && !isLoading

  if (isEmpty) {
    return <WelcomeScreen onSuggestionClick={onSuggestionClick} />
  }

  // Get the latest assistant message for showing follow-up suggestions
  const latestAssistantMessage = [...messages]
    .reverse()
    .find((m) => m.role === 'assistant')

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto custom-scrollbar"
    >
      <div className="min-h-full flex flex-col">
        {/* Messages */}
        <div className="flex-1">
          {messages.map((message, index) => (
            <div key={message.id}>
              <MessageBubble
                message={message}
                onCitationClick={onCitationClick}
                isLatest={index === messages.length - 1}
              />

              {/* Show follow-up suggestions after the latest assistant message */}
              {message.role === 'assistant' &&
                message.id === latestAssistantMessage?.id &&
                message.suggestedFollowups &&
                message.suggestedFollowups.length > 0 &&
                !isLoading && (
                  <div className="px-4 pb-4">
                    <div className="max-w-3xl mx-auto">
                      <div className="flex flex-wrap gap-2 stagger-children">
                        {message.suggestedFollowups.map((suggestion, i) => (
                          <button
                            key={i}
                            onClick={() => onSuggestionClick(suggestion)}
                            className="chip chip-amber"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && <LoadingSteps currentStep={loadingStep} />}
        </div>

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
