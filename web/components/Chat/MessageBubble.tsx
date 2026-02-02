'use client'

import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message, Citation } from '@/lib/types'

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
  onCitationClick,
  isLatest,
}: {
  content: string
  citations: Citation[]
  onCitationClick: (citationId: string) => void
  isLatest?: boolean
}) {
  // Process content to add citation markers
  const processedContent = useMemo(() => {
    if (!citations.length) return content

    // Replace [1], [2], etc. with special markers we can find in rendered output
    let processed = content
    citations.forEach((_, index) => {
      const num = index + 1
      // Replace various citation formats
      processed = processed.replace(
        new RegExp(`\\[${num}\\]`, 'g'),
        `<cite-marker data-num="${num}"></cite-marker>`
      )
    })
    return processed
  }, [content, citations])

  return (
    <div className={`py-6 px-4 ${isLatest ? 'message-enter' : ''}`}>
      <div className="max-w-3xl mx-auto">
        {/* Main content */}
        <div className="prose-chat">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Custom rendering for our citation markers
              p: ({ children, ...props }) => (
                <p {...props}>
                  {processChildren(children, citations, onCitationClick)}
                </p>
              ),
              li: ({ children, ...props }) => (
                <li {...props}>
                  {processChildren(children, citations, onCitationClick)}
                </li>
              ),
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
                Click numbered references to view
              </span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// Process React children to replace citation markers with clickable buttons
function processChildren(
  children: React.ReactNode,
  citations: Citation[],
  onCitationClick: (citationId: string) => void
): React.ReactNode {
  if (!children) return children

  if (typeof children === 'string') {
    // Check for our citation markers in the string
    const parts = children.split(/(<cite-marker[^>]*><\/cite-marker>)/g)

    if (parts.length === 1) return children

    return parts.map((part, i) => {
      const match = part.match(/<cite-marker data-num="(\d+)"><\/cite-marker>/)
      if (match) {
        const num = parseInt(match[1], 10)
        const citation = citations[num - 1]
        if (citation) {
          return (
            <button
              key={i}
              onClick={() => onCitationClick(citation.id)}
              className="citation-marker"
              aria-label={`View citation ${num}`}
            >
              {num}
            </button>
          )
        }
      }
      return part
    })
  }

  if (Array.isArray(children)) {
    return children.map((child, i) => (
      <span key={i}>{processChildren(child, citations, onCitationClick)}</span>
    ))
  }

  return children
}
