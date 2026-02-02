# Azure Deployment Design

## Overview

Deploy Lenny's Research Bot to Azure for online access as an internal tool.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Azure                                   │
│                                                                 │
│  ┌──────────────────────┐      ┌─────────────────────────────┐ │
│  │ Static Web Apps      │      │ Functions (Flex Consumption)│ │
│  │                      │      │                             │ │
│  │  Next.js Frontend    │─────▶│  /api/query                 │ │
│  │  (Auto-deployed      │ API  │  /api/research              │ │
│  │   from GitHub)       │      │  /api/health                │ │
│  │                      │      │                             │ │
│  └──────────────────────┘      │  ┌─────────────────────┐    │ │
│                                │  │ Bundled Index (32MB)│    │ │
│                                │  │ - pageindex.json    │    │ │
│                                │  │ - episode_index.json│    │ │
│                                │  │ - quotes/*.json     │    │ │
│                                │  └─────────────────────┘    │ │
│                                └──────────────┬──────────────┘ │
│                                               │                │
│                                               ▼                │
│                                ┌─────────────────────────────┐ │
│                                │ Azure OpenAI                │ │
│                                │ (Existing endpoint)         │ │
│                                └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Azure Functions (Flex Consumption)

- **Runtime**: Python 3.9+
- **Region**: Same as Azure OpenAI endpoint
- **Always-ready instances**: 1 (eliminates cold starts)
- **Max instances**: 10
- **Index data**: Bundled with function code (32MB)

### Azure Static Web Apps

- **Plan**: Free tier
- **Build preset**: Next.js
- **Source**: GitHub repo
- **App location**: `/web`
- **API**: Linked to Functions app (external backend)

## Environment Variables

### Functions App

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_API_KEY` | OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name |
| `AZURE_OPENAI_API_VERSION` | API version |
| `RETRIEVAL_MODE` | Set to `pageindex` |
| `PAGEINDEX_LOCAL_PATH` | Set to `./index` |

### Static Web Apps

| Variable | Description |
|----------|-------------|
| `BACKEND_URL` | Functions app URL (e.g., `https://<app>.azurewebsites.net`) |

## CI/CD

GitHub Actions workflows for automatic deployment on push to `main`:

1. **Functions**: Packages `functions/` + `index/` → deploys to Azure
2. **Static Web Apps**: Builds Next.js → deploys to edge

## Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| Static Web Apps (Free) | $0 |
| Functions (Flex Consumption, 1 always-ready) | ~$20-40 |
| Azure OpenAI | Usage-based (existing) |
| **Total** | ~$20-40/month |

## Setup Steps

1. Create Azure resource group
2. Create Azure Functions app (Flex Consumption plan)
3. Create Azure Static Web Apps resource linked to GitHub
4. Configure GitHub secrets for deployment
5. Add GitHub Actions workflow for Functions
6. Configure environment variables in Azure Portal
7. Test deployment
