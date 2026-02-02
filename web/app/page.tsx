'use client'

import { useCallback } from 'react'
import { useChat } from '@/hooks/useChat'
import { Header } from '@/components/Header'
import { ChatContainer } from '@/components/Chat'
import { ChatInput } from '@/components/Input'
import { CitationSidebar } from '@/components/Sidebar'

export default function Home() {
  const {
    messages,
    isLoading,
    loadingStep,
    error,
    sidebarOpen,
    activeCitation,
    allCitations,
    sendMessage,
    openCitation,
    closeSidebar,
    clearError,
    clearConversation,
  } = useChat()

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      sendMessage(suggestion)
    },
    [sendMessage]
  )

  return (
    <div className="h-screen flex flex-col bg-[var(--color-bg)]">
      {/* Header */}
      <Header
        onClearConversation={clearConversation}
        hasMessages={messages.length > 0}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-h-0">
        {/* Error Banner */}
        {error && (
          <div className="px-4 py-3 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
            <div className="max-w-3xl mx-auto flex items-center justify-between">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
              <button
                onClick={clearError}
                className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* Chat Area */}
        <ChatContainer
          messages={messages}
          isLoading={isLoading}
          loadingStep={loadingStep}
          onCitationClick={openCitation}
          onSuggestionClick={handleSuggestionClick}
        />

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading}
        />
      </main>

      {/* Citation Sidebar */}
      <CitationSidebar
        isOpen={sidebarOpen}
        citation={activeCitation}
        allCitations={allCitations}
        onClose={closeSidebar}
        onNavigate={openCitation}
      />
    </div>
  )
}
