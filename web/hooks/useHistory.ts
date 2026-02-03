'use client'

import { useState, useEffect, useCallback } from 'react'
import { HistoryEntry, PopularEntry } from '@/lib/types'
import { getHistory, getPopular } from '@/lib/api'

type UseHistoryResult = {
  history: HistoryEntry[]
  popular: PopularEntry[]
  isLoading: boolean
  refresh: () => Promise<void>
}

export function useHistory(): UseHistoryResult {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [popular, setPopular] = useState<PopularEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [historyData, popularData] = await Promise.all([
        getHistory(),
        getPopular(10),
      ])
      setHistory(historyData)
      setPopular(popularData)
    } catch (error) {
      console.error('Failed to fetch history/popular:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    history,
    popular,
    isLoading,
    refresh: fetchData,
  }
}
