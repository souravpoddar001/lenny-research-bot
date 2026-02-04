'use client'

import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message, Citation, ExecutiveSummary as ExecutiveSummaryType } from '@/lib/types'
import { ExecutiveSummary } from './ExecutiveSummary'

// Helper to escape special regex characters
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

type MessageBubbleProps = {
  message: Message
  onCitationClick: (citationId: string) => void
  isLatest?: boolean
}

export function MessageBubble({ message, onCitationClick, isLatest }: MessageBubbleProps) {
  if (message.role === 'user') {
    return <UserMessage content={message.content} />
  }

  return (
    <AssistantMessage
      content={message.content}
      citations={message.citations || []}
      executiveSummary={message.executiveSummary}
      onCitationClick={onCitationClick}
      isLatest={isLatest}
    />
  )
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end py-4 px-4 message-enter">
      <div className="max-w-[80%] md:max-w-[60%]">
        <div
          className="px-4 py-3 rounded-2xl rounded-br-md"
          style={{
            background: 'var(--color-amber-subtle)',
            color: 'var(--color-text-primary)',
          }}
        >
          <p className="whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    </div>
  )
}

function AssistantMessage({
  content,
  citations,
  executiveSummary,
  onCitationClick,
  isLatest,
}: {
  content: string
  citations: Citation[]
  executiveSummary?: ExecutiveSummaryType
  onCitationClick: (citationId: string) => void
  isLatest?: boolean
}) {
  // Process content to add clickable citation links
  const processedContent = useMemo(() => {
    if (!citations.length) return content

    let processed = content

    // Deduplicate citations by timestamp to avoid multiple replacements
    // (e.g., if same timestamp appears 5 times, we only want one replacement)
    const uniqueByTimestamp = new Map<string, Citation>()
    citations.forEach((citation) => {
      if (citation.timestamp && citation.youtube_link) {
        // Keep the first citation for each timestamp
        if (!uniqueByTimestamp.has(citation.timestamp)) {
          uniqueByTimestamp.set(citation.timestamp, citation)
        }
      }
    })

    // Replace inline citation timestamps [HH:MM:SS] with clickable links
    // Pattern: — Speaker, "Title" [HH:MM:SS]
    uniqueByTimestamp.forEach((citation) => {
      // Match the timestamp in brackets for this citation
      const timestampPattern = new RegExp(
        `\\[${escapeRegex(citation.timestamp)}\\]`,
        'g'
      )

      // Replace with a markdown link
      processed = processed.replace(
        timestampPattern,
        `[${citation.timestamp}](${citation.youtube_link})`
      )
    })

    return processed
  }, [content, citations])

  return (
    <div className={`py-6 px-4 ${isLatest ? 'message-enter' : ''}`}>
      <div className="max-w-3xl mx-auto">
        {/* Executive Summary */}
        {executiveSummary && <ExecutiveSummary summary={executiveSummary} />}

        {/* Main content */}
        <div className="prose-chat">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Make all links open in new tab
              a: ({ href, children, ...props }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="citation-link"
                  {...props}
                >
                  {children}
                </a>
              ),
              p: ({ children, ...props }) => <p {...props}>{children}</p>,
              li: ({ children, ...props }) => <li {...props}>{children}</li>,
              blockquote: ({ children, ...props }) => (
                <blockquote {...props}>{children}</blockquote>
              ),
            }}
          >
            {processedContent}
          </ReactMarkdown>
        </div>

        {/* Citation count indicator */}
        {citations.length > 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--color-border-subtle)]">
            <p className="text-sm text-[var(--color-text-muted)]">
              {citations.length} source{citations.length !== 1 ? 's' : ''} cited
              <span className="mx-2">·</span>
              <span className="text-[var(--color-violet)]">
                Click timestamps to watch on YouTube
              </span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

