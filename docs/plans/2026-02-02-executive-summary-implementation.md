# Executive Summary Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a visual executive summary (concept map + quote cards) to the top of research responses.

**Architecture:** Backend generates structured `executive_summary` JSON alongside prose via expanded synthesis prompts. Frontend renders SVG concept map with supporting points radiating from main insight, plus color-coded quote cards below.

**Tech Stack:** Python (Azure Functions), TypeScript/React (Next.js), SVG for visualization, Tailwind CSS

---

## Task 1: Add TypeScript Types

**Files:**
- Modify: `web/lib/types.ts`

**Step 1: Add executive summary types**

Add these types to `web/lib/types.ts`:

```typescript
export type SupportingPoint = {
  id: string
  label: string
  description: string
  color: string
}

export type KeyQuote = {
  text: string
  speaker: string
  timestamp: string
  youtube_link: string
  supports: string  // References SupportingPoint.id
}

export type ExecutiveSummary = {
  main_insight: string
  supporting_points: SupportingPoint[]
  key_quotes: KeyQuote[]
}
```

**Step 2: Update ResearchResponse type**

Update the existing `ResearchResponse` type to include the optional executive summary:

```typescript
export type ResearchResponse = {
  content: string
  citations: Omit<Citation, 'id'>[]
  sources: Source[]
  unverified_quotes?: string[]
  suggested_followups?: string[]
  executive_summary?: ExecutiveSummary  // Add this line
}
```

**Step 3: Update Message type**

Update the `Message` type to include executive summary:

```typescript
export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  sources?: Source[]
  suggestedFollowups?: string[]
  executiveSummary?: ExecutiveSummary  // Add this line
  timestamp: Date
}
```

**Step 4: Commit**

```bash
git add web/lib/types.ts
git commit -m "feat: add executive summary types"
```

---

## Task 2: Create QuoteCard Component

**Files:**
- Create: `web/components/Chat/QuoteCard.tsx`

**Step 1: Create the QuoteCard component**

Create `web/components/Chat/QuoteCard.tsx`:

```tsx
'use client'

import { KeyQuote } from '@/lib/types'

type QuoteCardProps = {
  quote: KeyQuote
  color: string
}

export function QuoteCard({ quote, color }: QuoteCardProps) {
  return (
    <div
      className="flex-1 min-w-[250px] max-w-[350px] p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
      style={{ borderLeftWidth: '4px', borderLeftColor: color }}
    >
      <p className="text-sm text-[var(--color-text-primary)] line-clamp-3 mb-3">
        "{quote.text}"
      </p>
      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--color-text-secondary)] font-medium">
          {quote.speaker}
        </span>
        <a
          href={quote.youtube_link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs px-2 py-1 rounded bg-[var(--color-violet-subtle)] text-[var(--color-violet)] hover:bg-[var(--color-violet)] hover:text-white transition-colors"
        >
          {quote.timestamp}
        </a>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add web/components/Chat/QuoteCard.tsx
git commit -m "feat: add QuoteCard component"
```

---

## Task 3: Create ConceptMap Component

**Files:**
- Create: `web/components/Chat/ConceptMap.tsx`

**Step 1: Create the ConceptMap component**

Create `web/components/Chat/ConceptMap.tsx`:

```tsx
'use client'

import { SupportingPoint } from '@/lib/types'

type ConceptMapProps = {
  mainInsight: string
  supportingPoints: SupportingPoint[]
}

export function ConceptMap({ mainInsight, supportingPoints }: ConceptMapProps) {
  const centerX = 200
  const centerY = 120
  const radius = 90

  // Calculate positions for supporting points around the center
  const getPointPosition = (index: number, total: number) => {
    const angle = (index * 2 * Math.PI) / total - Math.PI / 2  // Start from top
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    }
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox="0 0 400 240"
        className="w-full max-w-[500px] mx-auto h-auto"
        style={{ minHeight: '200px' }}
      >
        {/* Connecting lines */}
        {supportingPoints.map((point, index) => {
          const pos = getPointPosition(index, supportingPoints.length)
          return (
            <line
              key={`line-${point.id}`}
              x1={centerX}
              y1={centerY}
              x2={pos.x}
              y2={pos.y}
              stroke={point.color}
              strokeWidth="2"
              strokeOpacity="0.4"
            />
          )
        })}

        {/* Center node - Main Insight */}
        <circle
          cx={centerX}
          cy={centerY}
          r="50"
          fill="var(--color-surface)"
          stroke="var(--color-amber)"
          strokeWidth="3"
        />
        <foreignObject x={centerX - 45} y={centerY - 40} width="90" height="80">
          <div className="flex items-center justify-center h-full p-1">
            <p className="text-[10px] text-center text-[var(--color-text-primary)] font-medium leading-tight">
              {mainInsight.length > 60 ? mainInsight.slice(0, 60) + '...' : mainInsight}
            </p>
          </div>
        </foreignObject>

        {/* Supporting point nodes */}
        {supportingPoints.map((point, index) => {
          const pos = getPointPosition(index, supportingPoints.length)
          return (
            <g key={point.id}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r="35"
                fill="var(--color-surface)"
                stroke={point.color}
                strokeWidth="2"
              />
              <foreignObject x={pos.x - 32} y={pos.y - 28} width="64" height="56">
                <div className="flex items-center justify-center h-full p-1">
                  <p className="text-[9px] text-center text-[var(--color-text-secondary)] leading-tight">
                    {point.label}
                  </p>
                </div>
              </foreignObject>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add web/components/Chat/ConceptMap.tsx
git commit -m "feat: add ConceptMap SVG component"
```

---

## Task 4: Create ExecutiveSummary Container Component

**Files:**
- Create: `web/components/Chat/ExecutiveSummary.tsx`

**Step 1: Create the ExecutiveSummary component**

Create `web/components/Chat/ExecutiveSummary.tsx`:

```tsx
'use client'

import { ExecutiveSummary as ExecutiveSummaryType } from '@/lib/types'
import { ConceptMap } from './ConceptMap'
import { QuoteCard } from './QuoteCard'

type ExecutiveSummaryProps = {
  summary: ExecutiveSummaryType
}

export function ExecutiveSummary({ summary }: ExecutiveSummaryProps) {
  // Create a map of supporting point id to color
  const colorMap = new Map(
    summary.supporting_points.map((sp) => [sp.id, sp.color])
  )

  return (
    <div className="mb-6 p-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-[var(--color-amber)]" />
        <span className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wide">
          Executive Summary
        </span>
      </div>

      {/* Concept Map */}
      <ConceptMap
        mainInsight={summary.main_insight}
        supportingPoints={summary.supporting_points}
      />

      {/* Quote Cards */}
      {summary.key_quotes.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[var(--color-border-subtle)]">
          <div className="flex flex-wrap gap-3 justify-center">
            {summary.key_quotes.map((quote, index) => (
              <QuoteCard
                key={index}
                quote={quote}
                color={colorMap.get(quote.supports) || 'var(--color-border)'}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add web/components/Chat/ExecutiveSummary.tsx
git commit -m "feat: add ExecutiveSummary container component"
```

---

## Task 5: Update MessageBubble to Render Executive Summary

**Files:**
- Modify: `web/components/Chat/MessageBubble.tsx`

**Step 1: Import ExecutiveSummary component**

Add import at the top of `MessageBubble.tsx`:

```tsx
import { ExecutiveSummary } from './ExecutiveSummary'
```

**Step 2: Update MessageBubbleProps type**

Update the type to include executiveSummary:

```tsx
type MessageBubbleProps = {
  message: Message
  onCitationClick: (citationId: string) => void
  isLatest?: boolean
}
```

Note: The `Message` type already includes `executiveSummary` from Task 1.

**Step 3: Update AssistantMessage to render ExecutiveSummary**

In the `AssistantMessage` component, add `executiveSummary` prop and render it before the prose:

Update the AssistantMessage function signature:

```tsx
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
```

Add render of ExecutiveSummary before the main content div:

```tsx
return (
  <div className={`py-6 px-4 ${isLatest ? 'message-enter' : ''}`}>
    <div className="max-w-3xl mx-auto">
      {/* Executive Summary - render if present */}
      {executiveSummary && (
        <ExecutiveSummary summary={executiveSummary} />
      )}

      {/* Main content */}
      <div className="prose-chat">
        {/* ... existing ReactMarkdown code ... */}
      </div>

      {/* Citation count indicator */}
      {/* ... existing citation count code ... */}
    </div>
  </div>
)
```

**Step 4: Update MessageBubble to pass executiveSummary**

Update the call to AssistantMessage in MessageBubble:

```tsx
return (
  <AssistantMessage
    content={message.content}
    citations={message.citations || []}
    executiveSummary={message.executiveSummary}
    onCitationClick={onCitationClick}
    isLatest={isLatest}
  />
)
```

**Step 5: Add import for ExecutiveSummary type**

Update imports at top:

```tsx
import { Message, Citation, ExecutiveSummary as ExecutiveSummaryType } from '@/lib/types'
```

**Step 6: Commit**

```bash
git add web/components/Chat/MessageBubble.tsx
git commit -m "feat: render ExecutiveSummary in MessageBubble"
```

---

## Task 6: Update ChatContainer to Pass Executive Summary

**Files:**
- Modify: `web/components/Chat/ChatContainer.tsx`

**Step 1: Read current ChatContainer**

First, understand how messages are created from API responses.

**Step 2: Update message creation to include executiveSummary**

Find where the assistant message is created from the API response and add `executiveSummary`:

```tsx
const assistantMessage: Message = {
  id: `msg-${Date.now()}`,
  role: 'assistant',
  content: response.content,
  citations: response.citations.map((c, i) => ({ ...c, id: `cit-${i}` })),
  sources: response.sources,
  executiveSummary: response.executive_summary,  // Add this line
  timestamp: new Date(),
}
```

**Step 3: Commit**

```bash
git add web/components/Chat/ChatContainer.tsx
git commit -m "feat: pass executive_summary to Message from API response"
```

---

## Task 7: Update Backend ResearchOutput Dataclass

**Files:**
- Modify: `functions/shared/research.py`

**Step 1: Add executive summary to ResearchOutput dataclass**

Update the `ResearchOutput` dataclass:

```python
@dataclass
class ResearchOutput:
    """Result of deep research."""
    content: str
    citations: list[Citation]
    sources: list[dict]
    unverified_quotes: list[str] = field(default_factory=list)
    query_plan: Optional[QueryPlan] = None
    executive_summary: Optional[dict] = None  # Add this line

    def to_dict(self) -> dict:
        result = {
            "content": self.content,
            "citations": [c.to_dict() for c in self.citations],
            "sources": self.sources,
            "unverified_quotes": self.unverified_quotes,
        }
        if self.executive_summary:
            result["executive_summary"] = self.executive_summary
        return result
```

**Step 2: Commit**

```bash
git add functions/shared/research.py
git commit -m "feat: add executive_summary to ResearchOutput"
```

---

## Task 8: Update Synthesis Prompts for Executive Summary

**Files:**
- Modify: `functions/shared/research.py`

**Step 1: Update SYNTHESIS_PROMPT_ARTICLE**

Add executive summary instructions to the prompt. Replace the existing `SYNTHESIS_PROMPT_ARTICLE`:

```python
SYNTHESIS_PROMPT_ARTICLE = """You are a research assistant writing about product leadership insights from Lenny's Podcast.

Write a comprehensive article based on the provided transcript excerpts. Requirements:

1. CITATION RULES (CRITICAL):
   - Every factual claim must have a citation
   - Use format: — Speaker, "Episode Title" [HH:MM:SS]
   - Direct quotes must be EXACT - copy verbatim from the context
   - DO NOT paraphrase or modify quotes - use the exact words from the source
   - Wrap quotes in quotation marks

2. STRUCTURE:
   - Start with a compelling introduction
   - Organize into logical sections with headers
   - Include specific quotes from guests
   - End with key takeaways

3. STYLE:
   - Professional but accessible
   - Focus on actionable insights
   - Synthesize across multiple sources when relevant

4. EXECUTIVE SUMMARY (REQUIRED):
   After the article, output a JSON block tagged with ```executive_summary containing:
   - main_insight: One sentence core takeaway (max 80 chars)
   - supporting_points: Array of 3-4 objects with:
     - id: "sp1", "sp2", etc.
     - label: Short label (2-4 words)
     - description: One sentence explanation
     - color: Use these in order: "#8B5CF6", "#F59E0B", "#10B981", "#3B82F6"
   - key_quotes: Array of 2-3 best quotes with:
     - text: The exact quote (max 100 chars, truncate with ... if needed)
     - speaker: Speaker name
     - timestamp: HH:MM:SS format
     - youtube_link: Will be filled in by system
     - supports: Which supporting point id this evidences

Write the article now, followed by the executive_summary JSON block."""
```

**Step 2: Update SYNTHESIS_PROMPT_REPORT similarly**

Add the same executive summary section to the report prompt.

**Step 3: Update SYNTHESIS_PROMPT_QA similarly**

Add the same executive summary section to the QA prompt.

**Step 4: Commit**

```bash
git add functions/shared/research.py
git commit -m "feat: update synthesis prompts to request executive summary"
```

---

## Task 9: Parse Executive Summary from LLM Response

**Files:**
- Modify: `functions/shared/research.py`

**Step 1: Add helper function to parse executive summary**

Add this function to `research.py`:

```python
def _parse_executive_summary(self, content: str, citations: list[Citation]) -> tuple[str, Optional[dict]]:
    """
    Parse executive summary JSON from LLM response.

    Returns:
        Tuple of (content_without_json, executive_summary_dict)
    """
    import re

    # Look for ```executive_summary or ```json tagged block
    pattern = r'```(?:executive_summary|json)\s*(\{[\s\S]*?\})\s*```'
    match = re.search(pattern, content)

    if not match:
        return content, None

    # Extract JSON and clean content
    json_str = match.group(1)
    clean_content = content[:match.start()].rstrip()

    try:
        summary = json.loads(json_str)

        # Fill in youtube_links from citations
        citation_map = {c.timestamp: c.to_youtube_link() for c in citations}

        for quote in summary.get('key_quotes', []):
            timestamp = quote.get('timestamp', '')
            if timestamp in citation_map:
                quote['youtube_link'] = citation_map[timestamp]
            else:
                # Try to find a matching citation by speaker
                for c in citations:
                    if c.speaker == quote.get('speaker'):
                        quote['youtube_link'] = c.to_youtube_link()
                        break
                else:
                    quote['youtube_link'] = ''

        return clean_content, summary
    except json.JSONDecodeError:
        logger.warning("Failed to parse executive summary JSON")
        return content, None
```

**Step 2: Update _synthesize to use the parser**

In the `_synthesize` method, after getting the LLM response and before citation verification:

```python
content = response.choices[0].message.content

# Parse executive summary from response
content, executive_summary = self._parse_executive_summary(content, [])

# Verify and fix citations
fixed_content, citations, unverified = self.citation_verifier.verify_and_fix(
    content, chunks
)

# Update executive summary with youtube links now that we have citations
if executive_summary:
    citation_map = {c.timestamp: c.to_youtube_link() for c in citations}
    for quote in executive_summary.get('key_quotes', []):
        timestamp = quote.get('timestamp', '')
        if timestamp in citation_map:
            quote['youtube_link'] = citation_map[timestamp]
        elif not quote.get('youtube_link'):
            # Try to find by speaker
            for c in citations:
                if c.speaker == quote.get('speaker'):
                    quote['youtube_link'] = c.to_youtube_link()
                    break

# Add sources section
sources_section = self.citation_verifier.format_citations_section(citations)
final_content = fixed_content + sources_section

return ResearchOutput(
    content=final_content,
    citations=citations,
    sources=self._extract_sources(chunks),
    unverified_quotes=unverified,
    query_plan=plan,
    executive_summary=executive_summary,  # Add this
)
```

**Step 3: Commit**

```bash
git add functions/shared/research.py
git commit -m "feat: parse executive summary from LLM response"
```

---

## Task 10: Test End-to-End Locally

**Step 1: Start the backend**

```bash
cd functions
func start
```

**Step 2: Start the frontend**

```bash
cd web
npm run dev
```

**Step 3: Test a research query**

Open http://localhost:3000 and submit a query like "How do I find product-market fit?"

**Step 4: Verify executive summary renders**

- Concept map should appear with main insight in center
- 3-4 supporting points should radiate outward
- 2-3 quote cards should appear below with color-coded borders
- Clicking timestamps should open YouTube links

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: address integration issues from testing"
```

---

## Task 11: Final Commit and Push

**Step 1: Ensure all changes are committed**

```bash
git status
```

**Step 2: Push to remote**

```bash
git push origin main
```

**Step 3: Verify deployment**

Check that the CI/CD pipeline completes successfully and test on the deployed URL.
