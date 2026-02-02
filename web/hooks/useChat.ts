'use client'

import { useState, useCallback, useRef } from 'react'
import { Message, Citation, LoadingStep } from '@/lib/types'
import { sendResearchQuery, generateFollowups, isFollowUpQuery } from '@/lib/api'

type ChatState = {
  messages: Message[]
  isLoading: boolean
  loadingStep: LoadingStep | null
  error: string | null
  activeCitationId: string | null
  sidebarOpen: boolean
}

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    loadingStep: null,
    error: null,
    activeCitationId: null,
    sidebarOpen: false,
  })

  const loadingTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Simulate loading step progression
  const startLoadingSteps = useCallback(() => {
    const steps: LoadingStep[] = ['analyzing', 'searching', 'finding', 'synthesizing']
    let currentStep = 0

    setState((prev) => ({ ...prev, loadingStep: steps[0] }))

    loadingTimerRef.current = setInterval(() => {
      currentStep++
      if (currentStep < steps.length) {
        setState((prev) => ({ ...prev, loadingStep: steps[currentStep] }))
      }
    }, 8000) // Progress every 8 seconds (research takes 30-60s)
  }, [])

  const stopLoadingSteps = useCallback(() => {
    if (loadingTimerRef.current) {
      clearInterval(loadingTimerRef.current)
      loadingTimerRef.current = null
    }
    setState((prev) => ({ ...prev, loadingStep: null }))
  }, [])

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim() || state.isLoading) return

      // Create user message
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: query,
        timestamp: new Date(),
      }

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        error: null,
      }))

      startLoadingSteps()

      try {
        // Determine if this is a follow-up and include context if so
        const lastAssistantMessage = state.messages
          .filter((m) => m.role === 'assistant')
          .slice(-1)[0]

        let context: string | undefined
        if (lastAssistantMessage && isFollowUpQuery(query)) {
          // Summarize previous response as context (first 500 chars)
          context = lastAssistantMessage.content.slice(0, 500)
        }

        const response = await sendResearchQuery(query, context)

        // Add IDs to citations
        const citationsWithIds: Citation[] = response.citations.map((c, i) => ({
          ...c,
          id: `citation-${Date.now()}-${i}`,
        }))

        // Generate follow-up suggestions
        const suggestedFollowups = generateFollowups(query, response)

        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: response.content,
          citations: citationsWithIds,
          sources: response.sources,
          suggestedFollowups,
          executiveSummary: response.executive_summary,
          timestamp: new Date(),
        }

        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
          isLoading: false,
        }))
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: err instanceof Error ? err.message : 'An error occurred',
        }))
      } finally {
        stopLoadingSteps()
      }
    },
    [state.isLoading, state.messages, startLoadingSteps, stopLoadingSteps]
  )

  const openCitation = useCallback((citationId: string) => {
    setState((prev) => ({
      ...prev,
      activeCitationId: citationId,
      sidebarOpen: true,
    }))
  }, [])

  const closeSidebar = useCallback(() => {
    setState((prev) => ({
      ...prev,
      sidebarOpen: false,
      activeCitationId: null,
    }))
  }, [])

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }))
  }, [])

  const clearConversation = useCallback(() => {
    setState({
      messages: [],
      isLoading: false,
      loadingStep: null,
      error: null,
      activeCitationId: null,
      sidebarOpen: false,
    })
  }, [])

  // Get all citations from all messages
  const allCitations = state.messages
    .filter((m) => m.role === 'assistant')
    .flatMap((m) => m.citations || [])

  // Get the active citation object
  const activeCitation = allCitations.find((c) => c.id === state.activeCitationId)

  return {
    messages: state.messages,
    isLoading: state.isLoading,
    loadingStep: state.loadingStep,
    error: state.error,
    sidebarOpen: state.sidebarOpen,
    activeCitation,
    allCitations,
    sendMessage,
    openCitation,
    closeSidebar,
    clearError,
    clearConversation,
  }
}
