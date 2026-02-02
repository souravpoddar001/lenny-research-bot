# Lenny's Podcast Deep Research Bot

AI-powered research bot that searches Lenny's Podcast transcripts to generate long-form articles, research reports, and Q&A responses with accurate citations.

## Features

- **Deep Research Mode**: 4-stage retrieval pipeline for comprehensive analysis
- **Quick Q&A Mode**: Fast answers for simple questions
- **Citation Verification**: All quotes are verified against source material
- **YouTube Deep Links**: Clickable timestamps to exact moments in episodes
- **Multiple Output Types**: Articles, research reports, and Q&A responses

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WEB APPLICATION                          │
│                    Next.js on Azure Static Web Apps              │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AZURE FUNCTIONS (Python)                    │
│            /query (quick) | /research (deep) | /search          │
└─────────────┬─────────────────┬─────────────────┬───────────────┘
              │                 │                 │
              ▼                 ▼                 ▼
     ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
     │ Azure OpenAI   │ │ Azure AI Search│ │ Azure Blob     │
     │ (GPT-4o, Emb)  │ │ (Vector Index) │ │ (Transcripts)  │
     └────────────────┘ └────────────────┘ └────────────────┘
```

## Project Structure

```
lenny-research-bot/
├── infra/                      # Azure infrastructure (Bicep)
│   ├── main.bicep              # Main deployment template
│   └── search-index.json       # AI Search index schema
├── functions/                  # Azure Functions (Python)
│   ├── shared/
│   │   ├── chunking.py         # Transcript parsing & chunking
│   │   ├── embeddings.py       # Azure OpenAI embeddings
│   │   ├── search.py           # Azure AI Search client
│   │   ├── citations.py        # Citation verification
│   │   └── research.py         # Deep research pipeline
│   ├── function_app.py         # HTTP endpoints
│   ├── requirements.txt
│   └── host.json
├── web/                        # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── SearchBar.tsx
│   │   ├── ResearchOutput.tsx
│   │   └── CitationCard.tsx
│   └── package.json
└── scripts/
    └── ingest_transcripts.py   # Batch transcript ingestion
```

## Prerequisites

1. **Azure Subscription** with the following resources:
   - Azure OpenAI with deployments:
     - `gpt-4o` (for synthesis)
     - `gpt-4o-mini` (for analysis)
     - `text-embedding-3-small` (for embeddings)
   - Azure AI Search (Basic tier recommended)

2. **Transcript Repository**: Clone or download Lenny's Podcast transcripts

## Setup

### 1. Deploy Azure Infrastructure

```bash
# Create resource group
az group create -n lenny-research-rg -l eastus

# Deploy infrastructure
az deployment group create \
  -g lenny-research-rg \
  -f infra/main.bicep \
  --parameters openAiResourceName=<your-openai-resource>
```

### 2. Configure Environment

Create `functions/local.settings.json`:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_OPENAI_API_KEY": "<your-api-key>",
    "AZURE_OPENAI_ENDPOINT": "https://<your-resource>.openai.azure.com/",
    "AZURE_SEARCH_ENDPOINT": "https://<your-search>.search.windows.net",
    "AZURE_SEARCH_API_KEY": "<your-search-key>"
  }
}
```

### 3. Create Search Index

```bash
# Using Azure CLI
az search index create \
  --service-name <your-search-service> \
  --resource-group lenny-research-rg \
  --name lenny-transcripts-index \
  --fields @infra/search-index.json
```

### 4. Install Dependencies

```bash
# Python backend
cd functions
pip install -r requirements.txt

# Node.js frontend
cd ../web
npm install
```

### 5. Ingest Transcripts

```bash
# Dry run first
python scripts/ingest_transcripts.py \
  --transcripts-dir /path/to/episodes \
  --dry-run

# Full ingestion
python scripts/ingest_transcripts.py \
  --transcripts-dir /path/to/episodes \
  --output ingestion-report.json
```

### 6. Run Locally

```bash
# Terminal 1: Start Functions
cd functions
func start

# Terminal 2: Start Frontend
cd web
npm run dev
```

Visit `http://localhost:3000` to use the research bot.

## API Endpoints

| Endpoint | Method | Description | Response Time |
|----------|--------|-------------|---------------|
| `/api/health` | GET | Health check | <1s |
| `/api/query` | POST | Quick Q&A | <10s |
| `/api/research` | POST | Deep research | 30-60s |
| `/api/search` | POST | Direct search | <5s |

### Example Requests

**Quick Query:**
```bash
curl -X POST http://localhost:7071/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is product-market fit?"}'
```

**Deep Research:**
```bash
curl -X POST http://localhost:7071/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "How do top PMs think about product-market fit?"}'
```

## Cost Estimate

| Service | Configuration | Monthly Cost |
|---------|---------------|--------------|
| Azure AI Search | Basic tier | ~$73 |
| Azure OpenAI | GPT-4o-mini + GPT-4o | ~$8-12 |
| Azure Functions | Consumption | ~$0 |
| Azure Static Web Apps | Free tier | $0 |
| **Total** | | **~$80-85** |

## Deep Research Pipeline

The 4-stage pipeline ensures comprehensive, well-cited research:

1. **Query Analysis** (GPT-4o-mini)
   - Decompose query into sub-questions
   - Identify relevant topics and guests

2. **Broad Retrieval** (Azure AI Search)
   - Hybrid search (vector + keyword)
   - Retrieve topic segments for context

3. **Deep Retrieval** (Azure AI Search)
   - Search within identified transcripts
   - Extract speaker turns for quotes

4. **Synthesis** (GPT-4o)
   - Generate comprehensive output
   - Verify all citations against sources

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT
