# Executive Summary Visualization Design

**Date**: 2026-02-02
**Status**: Approved

## Overview

Add an executive summary visualization to the top of research responses, providing users with a quick-scan layer before the detailed prose.

## Problem

Research responses are comprehensive but verbose. Users need a way to quickly grasp the main insight and supporting evidence without reading the full response.

## Solution

A two-part visual executive summary:
1. **Concept Map**: Main insight in center, 2-4 supporting points radiating outward
2. **Quote Cards**: 2-3 key quotes below, color-coded to their supporting points

The existing full prose response remains unchanged below the visualization.

## Data Structure

New `executive_summary` field in the API response:

```json
{
  "content": "... existing full prose response ...",
  "citations": [...],
  "executive_summary": {
    "main_insight": "To find PMF, deeply satisfy a small group before scaling",
    "supporting_points": [
      {
        "id": "sp1",
        "label": "Satisfaction first",
        "description": "Focus on 3-5 customers who love it",
        "color": "#8B5CF6"
      },
      {
        "id": "sp2",
        "label": "Measure retention",
        "description": "30-50% 3-month retention signals PMF",
        "color": "#F59E0B"
      },
      {
        "id": "sp3",
        "label": "Efficiency last",
        "description": "It's OK to do things manually early",
        "color": "#10B981"
      }
    ],
    "key_quotes": [
      {
        "text": "Your job is to find three to five customers...",
        "speaker": "Todd Jackson",
        "timestamp": "00:21:44",
        "youtube_link": "https://youtube.com/watch?v=...&t=1304s",
        "supports": "sp1"
      }
    ]
  }
}
```

## Frontend Components

### ConceptMap.tsx
- SVG-based rendering
- Center circle: Main insight (larger, prominent)
- Radiating nodes: Supporting points with assigned colors
- Connecting lines from center to each supporting point

### QuoteCard.tsx
- Quote text snippet
- Speaker name + timestamp pill (clickable YouTube link)
- Left border accent using the color of its linked supporting point

### ExecutiveSummary.tsx
- Container component
- Renders ConceptMap above QuoteCards
- Responsive: cards row on desktop, stacked on mobile

### MessageBubble.tsx (update)
- Render ExecutiveSummary above prose when `executive_summary` is present

## Backend Changes

### research.py

**Prompt updates**: Modify `SYNTHESIS_PROMPT_ARTICLE`, `SYNTHESIS_PROMPT_REPORT`, and `SYNTHESIS_PROMPT_QA` to request executive summary JSON alongside prose.

**ResearchOutput update**: Add `executive_summary: Optional[dict]` field.

**Synthesis parsing**: Extract executive summary from LLM response, map youtube_links from citation data.

## Visual Design

### Color Palette (supporting points)
- Violet: `#8B5CF6`
- Amber: `#F59E0B`
- Emerald: `#10B981`
- Blue: `#3B82F6`

### Concept Map Layout
```
        [Supporting Point 1]
               |
               |
[SP4] ---- [MAIN INSIGHT] ---- [SP2]
               |
               |
        [Supporting Point 3]
```

### Quote Cards Layout
```
Desktop:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ ▎ Quote 1   │  │ ▎ Quote 2   │  │ ▎ Quote 3   │
│   Speaker   │  │   Speaker   │  │   Speaker   │
│   [00:21]   │  │   [00:45]   │  │   [01:12]   │
└─────────────┘  └─────────────┘  └─────────────┘

Mobile:
┌─────────────┐
│ ▎ Quote 1   │
└─────────────┘
┌─────────────┐
│ ▎ Quote 2   │
└─────────────┘
```

## Implementation Files

### Backend
- `functions/shared/research.py` - Prompt updates, response parsing

### Frontend
- `web/lib/types.ts` - New types
- `web/components/Chat/ExecutiveSummary.tsx` - New
- `web/components/Chat/ConceptMap.tsx` - New
- `web/components/Chat/QuoteCard.tsx` - New
- `web/components/Chat/MessageBubble.tsx` - Update
- `web/app/globals.css` - New styles

## Non-Goals

- Collapsible/accordion for the full prose (keep as-is)
- Interactive/animated concept map (static SVG is sufficient)
- Restructuring the prose to match supporting points
