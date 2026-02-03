# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lenny's Research Bot is an AI-powered research system that searches Lenny's Podcast transcripts to generate long-form articles, research reports, and Q&A responses with verified citations.

**Key Innovation:** The system uses **PageIndex** — a reasoning-based retrieval architecture that uses LLM navigation through a hierarchical index instead of traditional vector databases. This eliminates the need for embedding infrastructure while providing explainable retrieval.

## Commands

### Backend (Python Azure Functions)
```bash
cd lenny-research-bot/functions
pip install -r requirements.txt
func start                           # Start functions locally on port 7071
```

### Frontend (Next.js)
```bash
cd lenny-research-bot/web
npm install
npm run dev                          # Start dev server on port 3000
npm run build                        # Production build
npm run lint                         # Run ESLint
```

### Build PageIndex
```bash
# Build the hierarchical index from transcripts
python lenny-research-bot/scripts/build_pageindex.py --transcripts-dir /path/to/episodes --output-dir ./index
```

## Architecture

### System Flow
```
Next.js Frontend → Azure Functions (Python) → Azure Blob Storage (Cache/History)
                                            → PageIndex (LLM Reasoning Retrieval)
                                            → Azure OpenAI (Synthesis)
```

### PageIndex: Reasoning-Based Retrieval (`functions/shared/pageindex/`)

PageIndex replaces traditional vector search with LLM reasoning through a hierarchical index:

```
Query → LLM selects Themes → LLM selects Episodes → LLM selects Topics → Retrieve Quotes
```

**5-Stage Navigation:**
1. **Speaker Extraction**: Identifies if query asks about a specific guest
2. **Theme Selection**: LLM picks relevant themes from index
3. **Episode Selection**: LLM narrows down to specific episodes
4. **Topic Selection**: LLM identifies conversation topics within episodes
5. **Quote Retrieval**: Extracts actual quotes with speaker attribution

**Why PageIndex over Vector Search:**
- No vector database needed (~$73/month saved on Azure AI Search)
- No embedding API calls needed
- Explainable retrieval (reasoning trace shows WHY content was selected)
- Better handling of conceptual queries that use different words
- Speaker-aware navigation

### 4-Stage Deep Research Pipeline (`functions/shared/research.py`)
1. **Query Analysis**: Decomposes query into sub-questions, identifies topics/guests
2. **Broad Retrieval**: PageIndex navigates themes → episodes for context
3. **Deep Retrieval**: PageIndex drills into topics → quotes for citations
4. **Synthesis**: Generates output with citations, verifies quotes against sources

### Citation Verification (`functions/shared/citations.py`)
All generated quotes are verified against source chunks using fuzzy matching (rapidfuzz). Unverified quotes are flagged with `[⚠️ UNVERIFIED]`. Citations include YouTube deep links with timestamps.

### Hierarchical Index Structure (`index/`)
```
index/
├── themes.json              # Top-level themes with descriptions
├── episodes.json            # Episode metadata and summaries
├── themes/
│   └── {theme_id}.json      # Episodes grouped by theme
└── episodes/
    └── {episode_id}/
        ├── topics.json      # Conversation topics within episode
        └── quotes/
            └── {topic_id}.json  # Actual quotes with speaker attribution
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/query` | POST | Quick Q&A (single retrieval pass) |
| `/api/research` | POST | Deep research (full 4-stage pipeline) |
| `/api/history` | GET | Get session's query history (requires `X-Session-ID` header) |
| `/api/popular` | GET | Get popular queries by access count |
| `/api/cached` | GET | Get cached result by cache key (`?key=`) |

## Caching & History

### Query Result Caching (`functions/shared/cache.py`)
- Results cached in Azure Blob Storage container `research-cache`
- Cache key = SHA256 hash of normalized query (lowercase, trimmed)
- Includes `access_count` for popularity tracking
- Cache hit returns in ~2 seconds vs ~60 seconds for fresh query

### Session History (`functions/shared/history.py`)
- Per-user history stored in `research-history` container
- Anonymous session ID generated client-side (UUID in localStorage)
- Sent via `X-Session-ID` header on API requests
- Frontend sidebar shows "My History" + "Popular" queries

## Environment Variables

Required in `functions/local.settings.json`:
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT` - Model deployment name (e.g., "gpt-4o")
- `AZURE_STORAGE_CONNECTION_STRING` - For caching and history
- `PAGEINDEX_LOCAL_PATH` - Path to the hierarchical index (default: `../index`)

Optional (only if using vector mode instead of PageIndex):
- `RETRIEVAL_MODE` - Set to `vector` to use Azure AI Search instead of PageIndex
- `AZURE_SEARCH_ENDPOINT` - Only needed if RETRIEVAL_MODE=vector
- `AZURE_SEARCH_API_KEY` - Only needed if RETRIEVAL_MODE=vector

## Azure Deployment

### GitHub Actions
- Static Web App: `.github/workflows/azure-static-web-apps-*.yml`
- Functions: `.github/workflows/deploy-functions.yml`

### Manual Functions Deployment
If GitHub Actions deployment fails (404 errors), use manual deploy with remote build:
```bash
cd functions
func azure functionapp publish lenny-research-bot-func --python
```

**Known issue:** GitHub Actions workflow has `enable-oryx-build: false` which can cause deployment issues. Manual deploy uses remote build by default and is more reliable.

### Required Azure App Settings
For the Function App, ensure these are set in Azure Portal or via CLI:
```bash
az functionapp config appsettings set --name lenny-research-bot-func \
  --resource-group lenny-research-bot-rg \
  --settings "AZURE_STORAGE_CONNECTION_STRING=<connection-string>"
```

## Transcript Format

Transcripts are markdown files with YAML frontmatter:
```yaml
---
guest: "Guest Name"
title: "Episode Title"
youtube_url: "https://youtube.com/watch?v=..."
video_id: "..."
publish_date: "2024-01-01"
keywords: ["topic1", "topic2"]
---
```

Speaker turns can use either format:
- `Speaker Name (HH:MM:SS): dialogue text`
- `[HH:MM:SS] Speaker Name: dialogue text`
