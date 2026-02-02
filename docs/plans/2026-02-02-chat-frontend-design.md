# Chat Frontend Design

## Overview

Redesign the Lenny's Research Bot frontend from a search-based UI to a conversational chat interface, inspired by Microsoft Copilot with Lenny's brand warmth.

## Design Decisions

| Decision | Choice |
|----------|--------|
| Conversation model | Hybrid: single-turn for new topics, follow-ups reference previous response |
| Layout | Full-width with collapsible sidebar for citations |
| Color palette | Neutral base (Copilot-style) + Lenny's amber/orange accents |
| Input experience | Rich input with suggested follow-up chips after responses |
| Response display | Full response at once with progress steps during loading |
| Sidebar behavior | Click-to-reveal when citation markers clicked |

## Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Header (sticky): Logo + "Lenny's Research Bot" + theme    │
├─────────────────────────────────────────────────────────────┤
│                                                       │     │
│                    Chat Area                          │  S  │
│              (scrollable messages)                    │  i  │
│                                                       │  d  │
│    [User message bubble]                              │  e  │
│                                                       │  b  │
│    [Bot response with [1] [2] citation markers]       │  a  │
│                                                       │  r  │
│                                                       │     │
├─────────────────────────────────────────────────────────────┤
│  [Follow-up chips: "More on PMF" "Other guests"]           │
│  ┌─────────────────────────────────────────────────┐       │
│  │  Ask about Lenny's Podcast episodes...      [⏎] │       │
│  └─────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

- Chat area: max-width 800px centered for readability
- Sidebar: 480px, slides in from right when citation clicked

## Color Palette

```
Base:
- Background:     #FAFAFA (light) / #0F0F0F (dark)
- Surface:        #FFFFFF (light) / #1A1A1A (dark)
- Border:         #E5E5E5 (light) / #2A2A2A (dark)

Text:
- Primary:        #171717 (light) / #FAFAFA (dark)
- Secondary:      #737373 (light) / #A3A3A3 (dark)

Accent (Lenny's warmth):
- Primary:        #F59E0B (amber-500)
- Primary hover:  #D97706 (amber-600)
- Subtle:         #FEF3C7 (amber-100)

Secondary:
- Purple:         #8B5CF6 (citation markers)
```

## Components

### Message Bubbles
- User: Amber-tinted background, aligned right
- Bot: Full width, clean surface, subtle top border

### Citation Markers
- Purple pills `[1]` `[2]` inline in text
- Click opens sidebar to that citation

### Loading State
```
◉ Analyzing your question...
○ Searching 300+ episodes
○ Finding relevant quotes
○ Synthesizing response
```

### Suggested Follow-ups
- 2-4 contextual chips above input after each response
- Outlined pills with amber border

## State Management

```typescript
type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  sources?: Source[]
  suggestedFollowups?: string[]
  timestamp: Date
}

type ConversationState = {
  messages: Message[]
  isLoading: boolean
  loadingStep: 'analyzing' | 'searching' | 'synthesizing' | null
  activeCitationId: string | null
  sidebarOpen: boolean
}
```

## File Structure

```
web/
├── app/
│   ├── page.tsx              # Chat-based layout
│   ├── globals.css           # Color tokens, animations
│   └── layout.tsx            # Metadata
├── components/
│   ├── Chat/
│   │   ├── ChatContainer.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── CitationMarker.tsx
│   │   └── LoadingSteps.tsx
│   ├── Input/
│   │   ├── ChatInput.tsx
│   │   └── SuggestedChips.tsx
│   ├── Sidebar/
│   │   ├── CitationSidebar.tsx
│   │   └── CitationCard.tsx
│   └── Header.tsx
├── hooks/
│   └── useChat.ts
└── lib/
    └── api.ts
```

## Out of Scope

- Authentication/user accounts
- Conversation persistence
- Backend streaming
- Mobile-specific layout
